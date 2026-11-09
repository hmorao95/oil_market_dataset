# oil_market_dataset

[![CI](https://github.com/hmorao95/oil_market_dataset/actions/workflows/ci.yml/badge.svg)](https://github.com/hmorao95/oil_market_dataset/actions/workflows/ci.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)

Monthly oil market variables for structural VARs, January 1974 onward, built
from public sources with a small Python pipeline. These are the oil block
used in the oil production uncertainty paper. They follow the conventions of
Kilian and Murphy (2014) and Känzig (2021).

| column | series | unit | source |
|---|---|---|---|
| `poil` | real refiners' acquisition cost of imported crude oil | 100·ln(RAC / CPI × 100) | EIA `PET.R1300____3.M`, BLS `CUSR0000SA0` |
| `oilprod` | world crude oil production growth | 100·Δln | EIA international (crude incl. lease condensate) |
| `oilstocks` | change in global crude oil inventories | million barrels | EIA, Kilian and Murphy (2014) |
| `gecon` | world economic conditions indicator (WECI) | standardized | Baumeister, Korobilis and Lee (2022) |
| `gprh` | historical geopolitical risk index | 100·ln | Caldara and Iacoviello (2022) |

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for exact construction and caveats.

## Files

- `outputs/oil_market.csv`: the five series (`date` as `YYYY-MM`).
- `outputs/oil_market.xlsx`: sheet `data` with BEAR-style dates (`1977m1`), ready
  for the BEAR toolbox, and sheet `levels`.
- `outputs/oil_market_levels.csv`: the levels behind them (nominal RAC, CPI,
  world crude production in kb/d, global crude stocks in mb, WECI, GPRH).
- `data/raw/`: every source as a `period,value` CSV, as downloaded.

Series end at different months (ragged edge); missing months are blank.

## Quickstart

```python
import pandas as pd

df = pd.read_csv(
    "https://raw.githubusercontent.com/hmorao95/oil_market_dataset/main/outputs/oil_market.csv",
    index_col="date",
)
```

## Update

Requires [uv](https://docs.astral.sh/uv/) and a free EIA API key.

```bash
uv sync
export EIA_API_KEY=...        # PowerShell: $env:EIA_API_KEY = "..."
uv run oil-market refresh     # download to data/raw, rebuild outputs/
```

`uv run oil-market build` rebuilds `outputs/` from `data/raw` without network
access. The keyless BLS API allows 25 calls a day; set `BLS_API_KEY` (free) to
raise it, or keep the committed CPI with `--skip bls_cpi`.

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

See [AGENTS.md](AGENTS.md) for the full quality gate.

## Citation

Cite the dataset with [CITATION.cff](CITATION.cff), and cite the original sources:

- Baumeister, C., D. Korobilis and T. K. Lee (2022), "Energy markets and global
  economic conditions", *Review of Economics and Statistics* 104(4), 828–844.
- Caldara, D. and M. Iacoviello (2022), "Measuring geopolitical risk",
  *American Economic Review* 112(4), 1194–1225.
- Kilian, L. and D. P. Murphy (2014), "The role of inventories and speculative
  trading in the global market for crude oil", *Journal of Applied
  Econometrics* 29(3), 454–478.
- U.S. Energy Information Administration and U.S. Bureau of Labor Statistics.

## License

[CC BY 4.0](LICENSE). The source series remain subject to their providers' terms.
