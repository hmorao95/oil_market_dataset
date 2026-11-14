# Agent guide

Instructions for AI coding agents working in this repository. Human contributors
may find it useful too.

## What this is

`oil_market_dataset` publishes nine monthly oil market series for structural
VARs (`poil`, `oilprod`, `oilstocks`, `sprstocks`, `gecon`, `igrea`, `wipi`,
`gprh`, `etu`, from 1974m1), plus the small, typed Python package `oil_market`
that downloads the sources and builds them, with a python-fire CLI.

Layout:

- `src/oil_market/`: the package (`core.py` is the whole implementation;
  `__init__.py` re-exports; `__main__.py` enables `python -m`).
- `tests/`: network-free pytest suite (fake HTTP responses, synthetic raw
  files, and one regression test against the committed outputs).
- `data/raw/`: every source as a `period,value` CSV, as downloaded.
- `outputs/`: the published dataset. **Committed**: the data is the product.

## Setup

```bash
uv sync
uv run oil-market build              # offline, from data/raw
uv run oil-market refresh            # needs EIA_API_KEY
```

On a machine whose user path has non-ASCII characters, uv's editable install
may not be importable; `pytest` is unaffected (`pythonpath = ["src"]`), and
`PYTHONPATH=src uv run python -m oil_market ...` works.

## Quality gate (must pass before every commit)

CI runs exactly these; run them locally first:

```bash
uv run ruff check .
uv run ruff format --check .
uv run codespell src tests README.md CHANGELOG.md DATA_DICTIONARY.md AGENTS.md
uv run deptry src
uv run interrogate -c pyproject.toml src tests   # docstring coverage >= 95%
uv run mypy                                       # strict
uv run pytest                                     # coverage >= 90%
```

Do not weaken the gate to make it pass. Fix the code, or if a rule is genuinely
wrong for a case, add a narrowly-scoped ignore with a comment explaining why.

## Data updates

- Update with `uv run oil-market refresh`. Never edit `outputs/` by hand.
- `test_committed_outputs_match_raw` fails if `data/raw` changed but `outputs/`
  was not rebuilt: commit both together.
- The keyless BLS API allows 25 calls a day. If it is used up, run
  `refresh --skip bls_cpi` to keep the committed CPI.
- A data update bumps the minor version and updates the coverage period in
  `CITATION.cff` (title) and the repository's About description.
- Construction follows Kilian and Murphy (2014); do not change a series'
  definition without recording it in `DATA_DICTIONARY.md` and the changelog.

## Workflow

Branch (`feature/…`, `fix/…`, `data/…`), open a PR, squash-merge when CI is
green. Commit as the repository owner.
