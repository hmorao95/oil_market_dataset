"""Network-free tests for :mod:`oil_market`."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import requests

import oil_market
from oil_market import core

ROOT = Path(__file__).resolve().parents[1]


def monthly(start: str, values: list[float]) -> pd.Series:
    """Return a monthly series starting at ``start``."""
    return pd.Series(
        values, index=pd.period_range(start, periods=len(values), freq="M"), dtype=float
    )


def write_raw(raw: Path, n: int = 24) -> None:
    """Write a synthetic raw folder covering 1987-01 onward."""
    idx = pd.period_range("1987-01", periods=n, freq="M")
    rng = np.arange(1, n + 1, dtype=float)
    series = {
        "bls_cpi": 100 + rng,
        "eia_rac_imported": 20 + rng,
        "eia_world_crude": 60000 + 10 * rng,
        "eia_oecd_stocks": 3000 + 5 * rng,
        "eia_us_crude_stocks": 800000 + 1000 * rng,
        "eia_us_petroleum_stocks": 1600000 + 1000 * rng,
        "gpr_gprh": 90 + rng,
        "weci": rng / 10,
        "kilian_igrea": rng - 12,
        "bh_world_ip": 50 + rng,
    }
    for name, values in series.items():
        core.save_raw(name, pd.Series(values, index=idx), raw)


class FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(self, payload: object = None, content: bytes = b"") -> None:
        """Store the JSON payload and the raw body."""
        self.payload = payload
        self.content = content

    def json(self) -> object:
        """Return the JSON payload."""
        return self.payload

    def raise_for_status(self) -> None:
        """Never raise."""


# --------------------------------------------------------------------------- #
# transformations
# --------------------------------------------------------------------------- #
def test_global_crude_stocks_backcasts_and_scales() -> None:
    """OECD stocks are backcast before 1988m1 and scaled by the US crude share."""
    oecd = monthly("1987-06", [np.nan] * 7 + [1000.0, 1010.0])  # starts 1988-01
    us_total = monthly("1987-11", [400.0, 500.0, 500.0, 505.0])
    us_crude = monthly("1987-11", [200.0, 250.0, 300.0, 303.0])
    out = core.global_crude_stocks(oecd, us_crude, us_total)
    # 1987-11 is backcast with US total growth: 1000 * 400/500, then * 200/400.
    assert out.loc["1987-11"] == pytest.approx(1000 * 400 / 500 * 0.5)
    assert out.loc["1988-01"] == pytest.approx(1000 * 300 / 500)
    assert out.loc["1988-02"] == pytest.approx(1010 * 303 / 505)


def test_fill_months_is_log_linear() -> None:
    """A missing month is the geometric mean of its neighbours."""
    s = monthly("2025-09", [100.0, 121.0]).set_axis(
        pd.PeriodIndex(["2025-09", "2025-11"], freq="M")
    )
    filled = core.fill_months(s)
    assert list(filled.index.astype(str)) == ["2025-09", "2025-10", "2025-11"]
    assert filled.iloc[1] == pytest.approx(110.0)


def row(frame: pd.DataFrame, month: str) -> dict[str, float]:
    """Return one month of ``frame`` as plain floats."""
    values = frame.loc[[month]].to_numpy(dtype=float)[0]
    return dict(zip(map(str, frame.columns), values.tolist(), strict=True))


def test_build_formulas(tmp_path: Path) -> None:
    """Each output column follows its documented formula."""
    write_raw(tmp_path)
    data, levels = core.build(tmp_path)
    now, lvl, lag = row(data, "1988-03"), row(levels, "1988-03"), row(levels, "1988-02")
    poil = 100 * np.log(lvl["rac_imported"] / lvl["cpi"] * 100)
    assert now["poil"] == pytest.approx(poil)
    growth = lvl["world_crude_kbd"] / lag["world_crude_kbd"]
    assert now["oilprod"] == pytest.approx(100 * np.log(growth))
    change = lvl["global_crude_stocks_mb"] - lag["global_crude_stocks_mb"]
    assert now["oilstocks"] == pytest.approx(change)
    assert now["gprh"] == pytest.approx(100 * np.log(lvl["gprh"]))
    assert now["gecon"] == pytest.approx(lvl["weci"])
    assert now["igrea"] == pytest.approx(lvl["igrea"])
    assert now["wipi"] == pytest.approx(100 * np.log(lvl["world_ip"]))
    assert data.index.name == "date"
    assert list(data.columns) == [
        "poil",
        "oilprod",
        "oilstocks",
        "gecon",
        "igrea",
        "wipi",
        "gprh",
    ]


def test_write_and_read_outputs(tmp_path: Path) -> None:
    """Outputs round-trip, and the Excel sheet uses BEAR-style dates."""
    write_raw(tmp_path / "raw")
    data, levels = core.build(tmp_path / "raw")
    paths = core.write_outputs(data, levels, tmp_path / "out")
    assert [p.name for p in paths] == [
        "oil_market.csv",
        "oil_market_levels.csv",
        "oil_market.xlsx",
    ]
    back = core.read_output(paths[0])
    pd.testing.assert_frame_equal(back, data, check_freq=False, atol=1e-6)
    bear = pd.read_excel(paths[2], sheet_name="data", index_col=0)
    assert bear.index[0] == "1987m1"


# --------------------------------------------------------------------------- #
# parsers
# --------------------------------------------------------------------------- #
def xlsx(frame: pd.DataFrame, *, header: bool = True) -> bytes:
    """Serialize a frame to Excel bytes."""
    buf = io.BytesIO()
    frame.to_excel(buf, index=False, header=header)
    return buf.getvalue()


def test_parse_weci_reads_standardized_column() -> None:
    """The standardized WECI column is read with monthly periods."""
    frame = pd.DataFrame(
        [
            ["", "Global Economic Conditions Indicator", "Standardized GECON"],
            ["1973M2", 0.5, 1.1],
            ["1973M3", 0.2, 0.4],
        ]
    )
    s = core.parse_weci(xlsx(frame, header=False))
    assert list(s.index.astype(str)) == ["1973-02", "1973-03"]
    assert s.tolist() == [1.1, 0.4]


def test_parse_weci_layout_change() -> None:
    """A WECI file without the expected column raises SourceError."""
    frame = pd.DataFrame([["", "something else"], ["1973M2", 0.5]])
    with pytest.raises(core.SourceError, match="layout changed"):
        core.parse_weci(xlsx(frame, header=False))


def test_parse_gprh() -> None:
    """GPRH is read from the Caldara-Iacoviello file."""
    frame = pd.DataFrame(
        {"month": pd.to_datetime(["1900-01-01", "1900-02-01"]), "GPRH": [87.9, 86.5]}
    )
    s = core.parse_gprh(xlsx(frame))
    assert s.loc["1900-02"] == pytest.approx(86.5)


def test_parse_dated_column_reduces_to_months() -> None:
    """Mid-month dates map to their month, and the header row is skipped."""
    frame = pd.DataFrame(
        [
            ["Date", None],
            [pd.Timestamp("2026-07-01"), 1.0],
            [pd.Timestamp("2026-08-26"), 2.0],
        ]
    )
    s = core.parse_dated_column(xlsx(frame, header=False))
    assert list(s.index.astype(str)) == ["2026-07", "2026-08"]
    assert s.tolist() == [1.0, 2.0]


def test_parse_dated_column_no_dates() -> None:
    """A sheet without dates raises SourceError."""
    frame = pd.DataFrame([["Date", "value"], ["x", 1.0]])
    with pytest.raises(core.SourceError, match="No dated rows"):
        core.parse_dated_column(xlsx(frame, header=False))


# --------------------------------------------------------------------------- #
# download (HTTP faked)
# --------------------------------------------------------------------------- #
def test_eia_needs_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without EIA_API_KEY the EIA fetch fails with a clear message."""
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    with pytest.raises(core.SourceError, match="EIA_API_KEY"):
        core._eia("seriesid/X", {})


def test_eia_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty EIA response raises SourceError."""
    monkeypatch.setenv("EIA_API_KEY", "test")
    monkeypatch.setattr(
        requests, "get", lambda *_a, **_k: FakeResponse({"response": {"data": []}})
    )
    with pytest.raises(core.SourceError, match="no data"):
        core._eia("seriesid/X", {})


def test_bls_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refused BLS request (daily quota) raises SourceError."""
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    refused = {"status": "REQUEST_NOT_PROCESSED", "message": ["daily threshold"]}
    monkeypatch.setattr(requests, "post", lambda *_a, **_k: FakeResponse(refused))
    with pytest.raises(core.SourceError, match="daily threshold"):
        core.fetch_bls_cpi(2020, 2021)


def test_bls_skips_missing_and_annual(monkeypatch: pytest.MonkeyPatch) -> None:
    """BLS annual averages and unpublished months are dropped; the key is sent."""
    monkeypatch.setenv("BLS_API_KEY", "test")
    bodies: list[dict[str, Any]] = []
    obs = [
        {"year": "2025", "period": "M11", "value": "325.0"},
        {"year": "2025", "period": "M10", "value": "-"},
        {"year": "2025", "period": "M13", "value": "324.0"},
        {"year": "2025", "period": "M09", "value": "324.2"},
    ]

    def post(_url: str, json: dict[str, Any], **_k: Any) -> FakeResponse:
        bodies.append(json)
        return FakeResponse(
            {"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"data": obs}]}}
        )

    monkeypatch.setattr(requests, "post", post)
    s = core.fetch_bls_cpi(2025, 2025)
    assert list(s.index.astype(str)) == ["2025-09", "2025-11"]
    assert bodies[0]["registrationkey"] == "test"


def fake_get(url: str, params: dict[str, Any] | None = None, **_k: Any) -> FakeResponse:
    """Answer every source with a tiny valid payload."""
    if "api.eia.gov" in url:
        assert params is not None
        rows = [
            {"period": "1988-01", "value": "10"},
            {"period": "1988-02", "value": "NA"},
        ]
        return FakeResponse({"response": {"data": rows}})
    if url == core.GPR_URL:
        return FakeResponse(
            content=xlsx(
                pd.DataFrame({"month": pd.to_datetime(["1988-01-01"]), "GPRH": [80.0]})
            )
        )
    if url in {core.IGREA_URL, core.WIP_URL}:
        dated = pd.DataFrame([["Date", None], [pd.Timestamp("1988-01-26"), 1.5]])
        return FakeResponse(content=xlsx(dated, header=False))
    weci = pd.DataFrame([["", "Standardized GECON"], ["1988M1", 0.3]])
    return FakeResponse(content=xlsx(weci, header=False))


def test_download_writes_every_raw_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``download`` writes one CSV per source and drops EIA's NA values."""
    monkeypatch.setenv("EIA_API_KEY", "test")
    monkeypatch.setattr(requests, "get", fake_get)
    written = core.download(tmp_path, skip=("bls_cpi",))
    assert sorted(p.stem for p in written) == sorted(
        n for n in core.RAW_FILES if n != "bls_cpi"
    )
    stocks = core.read_raw("eia_oecd_stocks", tmp_path)
    assert stocks.to_dict() == {pd.Period("1988-01", "M"): 10.0}  # "NA" dropped


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_build_and_refresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The CLI builds outputs and passes --skip names to download."""
    raw, out = tmp_path / "raw", tmp_path / "out"
    write_raw(raw)
    cli = core._Cli()
    report = cli.build(str(raw), str(out))
    assert "oil_market.csv" in report
    assert re.search(r"poil\s+1987-01 to 1988-12", report)
    seen: list[tuple[str, ...]] = []

    def fake_download(raw_dir: Path, *, skip: tuple[str, ...] = ()) -> list[Path]:
        seen.append(skip)
        return [raw_dir / "x.csv"]

    monkeypatch.setattr(core, "download", fake_download)
    assert "x.csv" in cli.refresh(str(raw), str(out), skip="bls_cpi, weci")
    # python-fire hands ``--skip a,b`` over as a tuple.
    cli.download(str(raw), skip=("bls_cpi", "weci"))
    assert seen == [("bls_cpi", "weci"), ("bls_cpi", "weci")]
    with pytest.raises(core.SourceError, match="Unknown --skip"):
        cli.download(str(raw), skip="bls")


def test_main_runs_fire(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main`` hands the CLI class to python-fire."""
    calls: list[object] = []
    monkeypatch.setattr(
        "oil_market.core.fire.Fire", lambda component, **_k: calls.append(component)
    )
    core.main()
    assert calls == [core._Cli]


def test_main_exits_1_on_source_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main`` exits with code 1 on an expected error."""

    def fire(*_a: Any, **_k: Any) -> None:
        msg = "boom"
        raise core.SourceError(msg)

    monkeypatch.setattr("oil_market.core.fire.Fire", fire)
    with pytest.raises(SystemExit) as exc:
        core.main()
    assert exc.value.code == 1


# --------------------------------------------------------------------------- #
# repository
# --------------------------------------------------------------------------- #
def test_committed_outputs_match_raw() -> None:
    """``outputs/`` must be rebuilt whenever ``data/raw`` changes."""
    data, levels = core.build(ROOT / "data" / "raw")
    pd.testing.assert_frame_equal(
        core.read_output(ROOT / "outputs" / "oil_market.csv"),
        data,
        check_freq=False,
        atol=1e-6,
    )
    pd.testing.assert_frame_equal(
        core.read_output(ROOT / "outputs" / "oil_market_levels.csv"),
        levels,
        check_freq=False,
        atol=1e-6,
    )


def test_citation_version_matches_pyproject() -> None:
    """CITATION.cff carries the pyproject version."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)  # type: ignore[union-attr]
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f'version: "{version}"' in citation


def test_public_names() -> None:
    """Every name in __all__ is importable from the package."""
    assert set(oil_market.__all__) <= set(dir(oil_market))
