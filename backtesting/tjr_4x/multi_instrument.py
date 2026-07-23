"""Multi-instrument robustness harness (iteration 6).

Iteration 5 showed the C-bias + min-stop + 2R edge transfers from BTC to a
single ETH holdout but is fee-fragile and time-concentrated. The honest next
step (README verdict) is to broaden to MANY instruments and use an
equal-trade-count walk-forward. This module runs the SAME best config (never
retuned) across every distinct cached symbol and pools the closed trades so
``run_multi`` can measure breadth (how many instruments carry the edge) and
robustness (pooled walk-forward + cost-mix).

No network: everything reads the newest cached CSV per symbol via
``validation.run_symbol`` / ``load_5m``. Files that error out are skipped so
one bad cache never aborts the universe.
"""

from __future__ import annotations

import glob
import os
import re
from typing import Dict, List, Tuple

from .config import Config
from .engine import ClosedTrade, Result
from .validation import run_symbol, _CACHE


# Cache filename convention: <SYM>_USDT_USDT_5m_<since>_<until>.csv
_SYMBOL_RE = re.compile(r"^([A-Z0-9]+)_USDT_USDT_5m_", re.IGNORECASE)


def _symbol_of(path: str) -> str:
    """Extract the base symbol (e.g. ``BTC``) from a cache filename/path."""
    name = os.path.basename(path)
    m = _SYMBOL_RE.match(name)
    if m:
        return m.group(1).upper()
    # fallback: leading token before the first underscore
    return name.split("_", 1)[0].upper()


def _newest_per_symbol(cache_dir: str) -> Dict[str, str]:
    """Map each distinct symbol -> its NEWEST cached 5m CSV path (by mtime)."""
    matches = glob.glob(os.path.join(cache_dir, "*_5m_*.csv"))
    best: Dict[str, str] = {}
    for path in matches:
        sym = _symbol_of(path)
        if sym not in best or os.path.getmtime(path) > os.path.getmtime(best[sym]):
            best[sym] = path
    return best


def run_universe(cfg: Config,
                 cache_dir: str = "backtesting/tjr_4x/.cache",
                 ) -> Dict[str, Tuple[List[ClosedTrade], Result]]:
    """Run ``cfg`` (verbatim, no retuning) over each DISTINCT cached symbol.

    Uses the newest file per symbol. Returns ``{symbol: (closed, Result)}``.
    Any symbol whose load/detect/backtest raises is skipped (kept going) so a
    single corrupt or partially-downloaded cache never aborts the universe.
    No network.
    """
    # honour absolute or repo-relative cache_dir; fall back to the packaged one
    if not os.path.isdir(cache_dir):
        cache_dir = _CACHE

    universe: Dict[str, Tuple[List[ClosedTrade], Result]] = {}
    for sym in sorted(_newest_per_symbol(cache_dir)):
        try:
            out = run_symbol(f"*{sym}*_5m_*.csv", cfg)
        except Exception:
            continue  # skip errored files, keep going
        universe[sym] = (out["closed"], out["result"])
        # stash bar count on the Result for the per-instrument table
        setattr(universe[sym][1], "bars", out["bars"])
    return universe


def pooled_closed(universe: Dict[str, Tuple[List[ClosedTrade], Result]],
                  ) -> List[ClosedTrade]:
    """Concatenate closed trades across all symbols, sorted by entry_time."""
    pooled: List[ClosedTrade] = []
    for closed, _res in universe.values():
        pooled.extend(closed)
    pooled.sort(key=lambda c: c.entry_time)
    return pooled
