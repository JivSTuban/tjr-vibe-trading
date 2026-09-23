"""EOD 1% Previous-Low Reversal — backtest of the Design v1.0 spec.

Tests one claim: at 15:50 ET, buying a liquid US stock that is red, weak into the
bell, and sitting near its PREVIOUS day's low reaches a +1% target often enough to
pay for itself.

This package deliberately reuses `backtesting.eod_pressure_reversal` for prices,
intraday bars, universe, earnings and metrics. That study already solved the bar
convention, the split trap and the point-in-time universe; a second copy of them
would rot independently.
"""
