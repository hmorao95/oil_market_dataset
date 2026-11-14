# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Cite each EIA series (title, series ID, URL, access date) and the BLS CPI
  in the README and `CITATION.cff`, instead of one generic EIA entry.

### Fixed

- On Windows, a clone whose path has non-ASCII characters (such as
  `C:\Users\João\...`) left `oil_market` unimportable when `uv sync` built the
  environment on Python 3.10 or 3.11, which read the editable install's `.pth`
  file in the ANSI code page. The development environment now defaults to
  Python 3.12 (`.python-version`), which reads it as UTF-8. CI still runs the
  checks on 3.10. The README gives workarounds for 3.10 and 3.11.

## [0.4.0] - 2026-11-14

### Added

- `sprstocks`: monthly change in US SPR crude stocks (EIA `PET.MCSSTUS1.M`),
  million barrels, from 1977m11; the level is `spr_stocks_mb` in the levels
  file.

## [0.3.0] - 2026-11-09

### Added

- `etu`: energy transportation uncertainty index of Morão (2025), equal-weight
  `standardized` series from the `etu_world` repository.

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
