"""Pytest configuration for value_quality backtest package.

Makes backtesting.value_quality importable regardless of pytest rootdir.
"""

import os
import sys

# make value_quality importable regardless of pytest rootdir
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
