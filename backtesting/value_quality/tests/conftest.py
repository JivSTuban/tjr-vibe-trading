"""Pytest configuration for value_quality backtest package.

Makes ``backtesting.value_quality`` importable regardless of pytest rootdir
by putting the repo root on ``sys.path`` (``backtesting`` then resolves as a
PEP-420 namespace package). Mirrors the sys.path pattern in
``backtesting/tjr_4x/tests/conftest.py`` but targets the repo root so the
fully-qualified ``backtesting.value_quality`` import the brief requires works.
"""

import os
import sys

# repo root = tests/ -> value_quality/ -> backtesting/ -> <repo root>
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
