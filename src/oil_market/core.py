"""Build a monthly oil market dataset from public sources.

The dataset holds five series used in oil market VARs (Kilian and Murphy 2014;
Baumeister and Hamilton 2019; Känzig 2021):

- ``poil``: real refiners' acquisition cost of imported crude, 100*log.
- ``oilprod``: world crude oil production growth, 100*dlog.
- ``oilstocks``: change in global crude oil inventories, million barrels.
- ``gecon``: world economic conditions indicator (WECI), standardized.
- ``gprh``: historical geopolitical risk index, 100*log.

Every source is downloaded to ``data/raw`` as a two-column CSV
(``period,value``), and the dataset is rebuilt from those files only, so a
build is reproducible offline.

Examples:
    >>> from oil_market import download, build, write_outputs
    >>> download()  # needs EIA_API_KEY  # doctest: +SKIP
    >>> data, levels = build()  # doctest: +SKIP
    >>> write_outputs(data, levels)  # doctest: +SKIP
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
from pathlib import Path

import fire
import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
OUT_DIR = Path("outputs")
START = "1974-01"  # first month in which every series is available
TIMEOUT = 120
HEADERS = {
    "User-Agent": "oil-market-dataset (https://github.com/hmorao95/oil_market_dataset)"
}

EIA_URL = "https://api.eia.gov/v2"
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"
WECI_URL = (
    "https://drive.google.com/uc?export=download&id=1-xGp5-PvgjoAcDQuw09nq4Kgoj16hqsu"
)

#: Raw file name -> EIA series id (``seriesid`` route).
EIA_SERIES = {
    "eia_rac_imported": "PET.R1300____3.M",  # $/bbl
    "eia_us_crude_stocks": "PET.MCRSTUS1.M",  # thousand bbl, incl. SPR
    "eia_us_petroleum_stocks": "PET.MTTSTUS1.M",  # thousand bbl, incl. SPR
}
#: Raw file name -> EIA international facets (product, activity, region, unit).
EIA_INTL = {
    "eia_world_crude": ("57", "1", "WORL", "TBPD"),  # crude incl. condensate, kb/d
    "eia_oecd_stocks": ("5", "5", "OECD", "MBBL"),  # petroleum stocks, mb
}
BLS_CPI = "CUSR0000SA0"  # CPI-U, all items, seasonally adjusted, 1982-84=100
OECD_START = "1988-01"  # EIA OECD stocks have gaps and a level break before this

RAW_FILES = (*EIA_SERIES, *EIA_INTL, "bls_cpi", "gpr_gprh", "weci")


class SourceError(RuntimeError):
    """A source returned an error or an unexpected layout."""


# --------------------------------------------------------------------------- #
# download
# --------------------------------------------------------------------------- #
def _series(periods: list[str], values: list[object]) -> pd.Series:
    """Return a monthly series indexed by ``Period``, dropping missing values.

    Args:
        periods: Months as ``YYYY-MM`` strings.
        values: Values; anything not numeric (EIA's ``"NA"``) becomes missing.

    Returns:
        The sorted series.
    """
    s = pd.Series(
        pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(),
        index=pd.PeriodIndex(periods, freq="M"),
    )
    return s.dropna().sort_index()


def _eia(route: str, params: dict[str, str | int]) -> pd.Series:
    """Fetch one series from the EIA API v2.

    Args:
        route: API route after ``/v2/``.
        params: Query parameters other than the key.

    Returns:
        The monthly series.

    Raises:
        SourceError: If ``EIA_API_KEY`` is not set or the API returns no data.
    """
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        msg = "Set EIA_API_KEY (free key: https://www.eia.gov/opendata/)."
        raise SourceError(msg)
    r = requests.get(
        f"{EIA_URL}/{route}",
        params={"api_key": key, "length": 5000, **params},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    rows = r.json().get("response", {}).get("data", [])
    if not rows:
        msg = f"EIA returned no data for {route} {params}."
        raise SourceError(msg)
    return _series([row["period"] for row in rows], [row["value"] for row in rows])


def fetch_bls_cpi(start: int = 1970, end: int | None = None) -> pd.Series:
    """Fetch the seasonally adjusted CPI-U from the BLS API.

    The keyless API allows 10 years per call and 25 calls a day; set
    ``BLS_API_KEY`` (free) for 20 years per call and 500 calls a day. Months
    BLS did not publish (October 2025) are left out.

    Args:
        start: First year.
        end: Last year; the current year when ``None``.

    Returns:
        The monthly CPI.

    Raises:
        SourceError: If the API refuses the request.
    """
    end = end or pd.Timestamp.now(tz="UTC").year
    key = os.environ.get("BLS_API_KEY", "").strip()
    step = 20 if key else 10
    periods: list[str] = []
    values: list[object] = []
    for y0 in range(start, end + 1, step):
        body: dict[str, object] = {
            "seriesid": [BLS_CPI],
            "startyear": str(y0),
            "endyear": str(min(y0 + step - 1, end)),
        }
        if key:
            body["registrationkey"] = key
        js = requests.post(BLS_URL, json=body, timeout=TIMEOUT).json()
        if js.get("status") != "REQUEST_SUCCEEDED":
            msg = f"BLS API: {js.get('message')}"
            raise SourceError(msg)
        for obs in js["Results"]["series"][0]["data"]:
            if obs["period"] != "M13":
                periods.append(f"{obs['year']}-{obs['period'][1:]}")
                values.append(obs["value"])
    return _series(periods, values)


def parse_gprh(content: bytes) -> pd.Series:
    """Read GPRH from the Caldara-Iacoviello ``data_gpr_export.xls`` file.

    Args:
        content: The downloaded file.

    Returns:
        The monthly historical GPR index.
    """
    d = pd.read_excel(io.BytesIO(content))
    months = pd.to_datetime(d["month"]).dt.strftime("%Y-%m").tolist()
    return _series(months, d["GPRH"].tolist())


def parse_weci(content: bytes) -> pd.Series:
    """Read the standardized WECI from Baumeister's ``GECON_indicator.xlsx``.

    Args:
        content: The downloaded file.

    Returns:
        The column "Standardized GECON".

    Raises:
        SourceError: If the column is missing.
    """
    d = pd.read_excel(io.BytesIO(content), header=None)
    header = [str(h).strip() for h in d.iloc[0]]
    if "Standardized GECON" not in header:
        msg = f"WECI file layout changed; header is {header}."
        raise SourceError(msg)
    col = header.index("Standardized GECON")
    rows = d.iloc[1:]
    rows = rows[rows[0].astype(str).str.fullmatch(r"\d{4}M\d{1,2}")]
    months = [
        f"{y}-{int(m):02d}" for y, m in (s.split("M") for s in rows[0].astype(str))
    ]
    return _series(months, rows[col].tolist())


def _get(url: str) -> bytes:
    """Download a file.

    Args:
        url: Address.

    Returns:
        The response body.
    """
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def save_raw(name: str, series: pd.Series, raw_dir: Path = RAW_DIR) -> Path:
    """Write a raw series as ``period,value`` CSV.

    Args:
        name: File stem.
        series: Monthly series.
        raw_dir: Folder.

    Returns:
        The file written.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{name}.csv"
    out = pd.DataFrame({"period": series.index.astype(str), "value": series.to_numpy()})
    out.to_csv(path, index=False, lineterminator="\n")
    return path


def download(raw_dir: Path = RAW_DIR, *, skip: tuple[str, ...] = ()) -> list[Path]:
    """Download every source to ``raw_dir``.

    Args:
        raw_dir: Folder for the raw CSVs.
        skip: Raw file names to leave as they are (e.g. ``("bls_cpi",)`` when
            the keyless BLS quota is used up).

    Returns:
        The files written.
    """
    written = []
    for name in RAW_FILES:
        if name in skip:
            continue
        logger.info("downloading %s", name)
        written.append(save_raw(name, _fetch(name), raw_dir))
    return written


def _fetch(name: str) -> pd.Series:
    """Fetch one source by its raw file name.

    Args:
        name: One of :data:`RAW_FILES`.

    Returns:
        The monthly series.
    """
    if name in EIA_SERIES:
        return _eia(f"seriesid/{EIA_SERIES[name]}", {})
    if name in EIA_INTL:
        product, activity, region, unit = EIA_INTL[name]
        return _eia(
            "international/data/",
            {
                "frequency": "monthly",
                "data[]": "value",
                "facets[productId][]": product,
                "facets[activityId][]": activity,
                "facets[countryRegionId][]": region,
                "facets[unit][]": unit,
            },
        )
    if name == "bls_cpi":
        return fetch_bls_cpi()
    if name == "gpr_gprh":
        return parse_gprh(_get(GPR_URL))
    return parse_weci(_get(WECI_URL))


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def read_raw(name: str, raw_dir: Path = RAW_DIR) -> pd.Series:
    """Read a raw CSV written by :func:`save_raw`.

    Args:
        name: File stem.
        raw_dir: Folder.

    Returns:
        The monthly series.
    """
    d = pd.read_csv(raw_dir / f"{name}.csv", dtype={"period": str})
    return _series(d["period"].tolist(), d["value"].tolist())


def fill_months(series: pd.Series) -> pd.Series:
    """Fill months missing inside a series by log-linear interpolation.

    Used for the CPI, which BLS did not publish for October 2025.

    Args:
        series: Positive monthly series.

    Returns:
        The series on a complete monthly index.
    """
    full = pd.period_range(series.index[0], series.index[-1], freq="M")
    return pd.Series(np.exp(np.log(series.reindex(full)).interpolate()), index=full)


def global_crude_stocks(
    oecd: pd.Series, us_crude: pd.Series, us_total: pd.Series
) -> pd.Series:
    """Global crude oil inventories, as in Kilian and Murphy (2014).

    OECD petroleum stocks are used from 1988m1 and extended backward with the
    growth rate of US total petroleum stocks. They are then scaled by the US
    ratio of crude oil stocks to total petroleum stocks.

    Args:
        oecd: OECD petroleum stocks, million barrels.
        us_crude: US crude oil stocks including the SPR, million barrels.
        us_total: US crude oil and petroleum product stocks including the
            SPR, million barrels.

    Returns:
        Global crude oil stocks, million barrels.
    """
    oecd = oecd.loc[OECD_START:]
    back = us_total.loc[: oecd.index[0]]
    extended = pd.concat([oecd.iloc[0] * back / back.iloc[-1], oecd.iloc[1:]])
    stocks: pd.Series = (extended * us_crude / us_total).dropna()
    return stocks


def build(raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the dataset from the raw CSVs.

    Args:
        raw_dir: Folder with the raw CSVs.

    Returns:
        ``(data, levels)``: the five VAR series, and the levels they come from.
    """
    cpi = fill_months(read_raw("bls_cpi", raw_dir))
    rac = read_raw("eia_rac_imported", raw_dir)
    world = read_raw("eia_world_crude", raw_dir)
    stocks = global_crude_stocks(
        read_raw("eia_oecd_stocks", raw_dir),
        read_raw("eia_us_crude_stocks", raw_dir) / 1000,
        read_raw("eia_us_petroleum_stocks", raw_dir) / 1000,
    )
    gprh = read_raw("gpr_gprh", raw_dir)
    weci = read_raw("weci", raw_dir)
    levels = pd.DataFrame(
        {
            "rac_imported": rac,
            "cpi": cpi,
            "world_crude_kbd": world,
            "global_crude_stocks_mb": stocks,
            "weci": weci,
            "gprh": gprh,
        }
    )
    data = pd.DataFrame(
        {
            "poil": 100 * np.log(rac / cpi * 100),
            "oilprod": 100 * np.log(world).diff(),
            "oilstocks": stocks.diff(),
            "gecon": weci,
            "gprh": 100 * np.log(gprh),
        }
    )
    return _trim(data), _trim(levels)


def _trim(df: pd.DataFrame) -> pd.DataFrame:
    """Keep months from :data:`START` to the last month with any data.

    Args:
        df: Monthly frame.

    Returns:
        The trimmed frame, index named ``date``.
    """
    df = df.loc[START:].dropna(how="all")
    df.index.name = "date"
    return df


def write_outputs(
    data: pd.DataFrame, levels: pd.DataFrame, out_dir: Path = OUT_DIR
) -> list[Path]:
    """Write the dataset as CSV and as an Excel file.

    The Excel file has a ``data`` sheet with BEAR-style dates (``1977m1``),
    ready for the BEAR toolbox, and a ``levels`` sheet.

    Args:
        data: The five VAR series.
        levels: The underlying levels.
        out_dir: Folder.

    Returns:
        The files written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        out_dir / "oil_market.csv",
        out_dir / "oil_market_levels.csv",
        out_dir / "oil_market.xlsx",
    ]
    data.to_csv(paths[0], float_format="%.6f", lineterminator="\n")
    levels.to_csv(paths[1], float_format="%.6f", lineterminator="\n")
    bear = data.copy()
    bear.index = [f"{p.year}m{p.month}" for p in data.index]
    with pd.ExcelWriter(paths[2]) as xl:
        bear.to_excel(xl, sheet_name="data")
        levels.to_excel(xl, sheet_name="levels")
    return paths


def read_output(path: Path = OUT_DIR / "oil_market.csv") -> pd.DataFrame:
    """Read a CSV written by :func:`write_outputs`.

    Args:
        path: CSV file.

    Returns:
        The frame indexed by month.
    """
    d = pd.read_csv(path, index_col="date")
    d.index = pd.PeriodIndex(d.index, freq="M")
    return d


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
class _Cli:
    """Oil market dataset: ``download``, ``build`` or ``refresh``."""

    def download(  # ruff: ignore[no-self-use] - python-fire exposes methods
        self, raw_dir: str = str(RAW_DIR), skip: str = ""
    ) -> str:
        """Download every source to ``raw_dir``.

        Args:
            raw_dir: Folder for the raw CSVs.
            skip: Comma-separated raw file names to leave as they are.

        Returns:
            The files written.
        """
        names = tuple(s.strip() for s in re.split(r"[,\s]+", skip) if s.strip())
        return "\n".join(str(p) for p in download(Path(raw_dir), skip=names))

    def build(  # ruff: ignore[no-self-use] - python-fire exposes methods
        self, raw_dir: str = str(RAW_DIR), out_dir: str = str(OUT_DIR)
    ) -> str:
        """Rebuild ``outputs/`` from the raw CSVs.

        Args:
            raw_dir: Folder with the raw CSVs.
            out_dir: Output folder.

        Returns:
            The files written and the coverage of each series.
        """
        data, levels = build(Path(raw_dir))
        paths = write_outputs(data, levels, Path(out_dir))
        cover = [
            f"{c!s:10s} {s.first_valid_index()!s} to {s.last_valid_index()!s}"
            for c, s in data.items()
        ]
        return "\n".join([*map(str, paths), "", *cover])

    def refresh(
        self, raw_dir: str = str(RAW_DIR), out_dir: str = str(OUT_DIR), skip: str = ""
    ) -> str:
        """Download, then build.

        Args:
            raw_dir: Folder for the raw CSVs.
            out_dir: Output folder.
            skip: Comma-separated raw file names to leave as they are.

        Returns:
            What ``download`` and ``build`` report.
        """
        return self.download(raw_dir, skip) + "\n\n" + self.build(raw_dir, out_dir)


def main() -> None:
    """Run the command-line interface."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        fire.Fire(_Cli, name="oil-market")
    except (SourceError, requests.RequestException, OSError) as exc:
        logger.error("%s", exc)  # ruff: ignore[error-instead-of-exception] - one line, no traceback
        sys.exit(1)
