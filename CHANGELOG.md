# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-09

### Added

- `igrea`: Kilian's (2009) index of global real economic activity (Dallas Fed).
- `wipi`: Baumeister and Hamilton (2019) OECD+6 industrial production, 100·ln.

### Fixed

- `--skip a,b` on the command line: python-fire passes it as a tuple, which
  crashed `download` and `refresh`. Unknown names now raise a clear error.

## [0.1.0] - 2026-11-09

### Added

- Five monthly series from 1974m1: `poil`, `oilprod`, `oilstocks`, `gecon`,
  `gprh`, as CSV and as a BEAR-ready Excel file, plus their levels.
- `oil_market` package and `oil-market` CLI (`download`, `build`, `refresh`).
- Raw source extracts in `data/raw/` (EIA, BLS, Baumeister, Caldara-Iacoviello).
