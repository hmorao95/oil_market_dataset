"""
Module entry point enabling ``python -m oil_market``.

Delegates to :func:`oil_market.core.main`, the same as the ``oil-market``
console script.
"""

from __future__ import annotations

from oil_market.core import main

if __name__ == "__main__":
    main()
