"""
Public package interface for :mod:`oil_market`.

This package downloads and builds a monthly oil market dataset (real oil price,
world oil production, global crude inventories, global economic conditions and
geopolitical risk) from public sources. The implementation lives in
:mod:`oil_market.core`; the names most callers need are re-exported here.

Exports:
    download: Download every source to ``data/raw``.
    build: Build the dataset from the raw files.
    write_outputs: Write the CSV and Excel outputs.
    read_output: Read a published CSV back.
    read_raw: Read one raw CSV.
    fetch_bls_cpi: Fetch the CPI from the BLS API.
    parse_gprh: Read GPRH from the Caldara-Iacoviello file.
    parse_weci: Read the standardized WECI from Baumeister's file.
    global_crude_stocks: Kilian-Murphy global crude inventory proxy.
    fill_months: Log-linear fill of missing months.
    SourceError: Raised when a source fails.
    RAW_DIR, OUT_DIR, RAW_FILES: Default paths and raw file names.
    main: Entry point for the ``python-fire`` command-line interface.
"""

from __future__ import annotations

from oil_market.core import (
    OUT_DIR,
    RAW_DIR,
    RAW_FILES,
    SourceError,
    build,
    download,
    fetch_bls_cpi,
    fill_months,
    global_crude_stocks,
    main,
    parse_gprh,
    parse_weci,
    read_output,
    read_raw,
    write_outputs,
)

__all__ = [
    "OUT_DIR",
    "RAW_DIR",
    "RAW_FILES",
    "SourceError",
    "build",
    "download",
    "fetch_bls_cpi",
    "fill_months",
    "global_crude_stocks",
    "main",
    "parse_gprh",
    "parse_weci",
    "read_output",
    "read_raw",
    "write_outputs",
]
