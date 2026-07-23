"""TJR 4X look-ahead-safe event backtester.

One approved TJR setup (decision 0001): daily-bias-aligned liquidity
sweep -> body-close BOS/MSS confirmation -> entry on return into an
FVG/OB from the displacement leg, SL beyond the sweep + buffer, TP at
fixed 2R. See ``strategy.find_trades`` and ``engine.backtest``.
"""

from .config import Config
from .strategy import Trade, find_trades
from .engine import Result, backtest

__all__ = ["Config", "Trade", "find_trades", "Result", "backtest"]
