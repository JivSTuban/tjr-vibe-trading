"""Look-ahead-safe TJR 4X setup detection.

Pivot-confirmation lag (READ THIS):
    A pivot with ``swing_length`` bars on each side can only be *known*
    to be a pivot once ``swing_length`` bars have printed AFTER it. So a
    swing at positional bar ``p`` is not confirmed until bar
    ``p + swing_length``. A liquidity sweep of that swing, and any BOS
    that confirms after the sweep, are therefore anchored at their own
    COMPLETION bars (``Swept`` bar for the sweep, ``BrokenIndex`` for the
    BOS) -- never at the pivot bar. We additionally require the
    confirmation (BOS) bar to be ``>= pivot_bar + swing_length`` so a
    trade is only ever *created* from information available at or before
    its confirmation bar. The entry fill and SL/TP resolution then happen
    on strictly LATER 5m bars (handled by ``engine.backtest``). This is
    what makes the backtest causal / non-repainting.

Pipeline (all on the SAME instrument, only resampling from 5m):
    1. 5m -> 1D daily bias (sign of last confirmed daily BOS; else
       ``bias_lookback_days`` HH/HL slope).
    2. 5m -> 15m setup frame. On the 15m frame:
         a. detect pivot-3 swings (smc.swing_highs_lows).
         b. detect a liquidity sweep = wick pierces a swing level AND a
            body closes back beyond it within ``sweep_close_back_bars``.
         c. require a same-direction body-close BOS/MSS AFTER the sweep.
         d. require an FVG or OB (from the post-BOS displacement) that
            price can return into -> its edge is the entry.
    3. Emit a ``Trade`` whose ``entry_time`` is the OPEN of the 5m bar
       immediately after the confirmation 15m bar closes (so fills are
       resolved forward-only in the engine).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd
from smartmoneyconcepts import smc


# --------------------------------------------------------------------------- #
# Trade record
# --------------------------------------------------------------------------- #
@dataclass
class Trade:
    entry_time: pd.Timestamp   # first 5m bar eligible to fill the entry
    direction: int             # +1 long, -1 short
    entry: float               # zone edge (limit price)
    sl: float
    tp: float
    sweep_level: float         # swing level that was swept
    bos_index: int             # positional bar (on 15m frame) of the confirming BOS
    confirm_time: pd.Timestamp = None  # close time of the confirming 15m bar


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_OHLC = ["open", "high", "low", "close", "volume"]


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase OHLCV columns, sorted datetime index, dropna."""
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    missing = [c for c in _OHLC if c not in out.columns]
    if missing:
        raise ValueError(f"missing OHLCV columns: {missing}")
    if not isinstance(out.index, pd.DatetimeIndex):
        raise ValueError("df index must be a DatetimeIndex")
    return out[_OHLC].sort_index()


# ccxt-style timeframe -> pandas offset alias. Critical: pandas treats
# "15m" as 15 MONTHS; minutes must be "15min". Days/weeks map straight.
_TF_TO_PANDAS = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h",
    "1d": "1D", "1D": "1D", "1w": "1W", "1W": "1W",
}


def _to_pandas_rule(rule: str) -> str:
    return _TF_TO_PANDAS.get(rule, rule)


def _resample(df5m: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum"}
    prule = _to_pandas_rule(rule)
    out = df5m.resample(prule, label="left", closed="left").agg(agg).dropna(how="any")
    return out


def compute_bias(df5m: pd.DataFrame, cfg) -> pd.Series:
    """Daily bias series indexed by daily bar start.

    +1 bullish / -1 bearish / 0 neutral. Uses the sign of the last
    *confirmed* daily BOS as of each day; falls back to the slope of a
    rolling HH/HL over ``bias_lookback_days`` when no BOS is confirmed
    yet. Every value at day D uses only data available at the close of
    day D (BOS confirmed at bar b applies from bar b onward).
    """
    daily = _resample(df5m, cfg.bias_timeframe)
    bias = pd.Series(0, index=daily.index, dtype=int)
    if len(daily) < 2:
        return bias

    # HH/HL slope fallback: compare rolling highs/lows now vs lookback ago.
    lb = cfg.bias_lookback_days
    roll_hi = daily["high"].rolling(lb, min_periods=2).max()
    roll_lo = daily["low"].rolling(lb, min_periods=2).min()
    slope = np.sign(
        (roll_hi - roll_hi.shift(lb)).fillna(0)
        + (roll_lo - roll_lo.shift(lb)).fillna(0)
    ).astype(int)
    bias.loc[:] = slope.values

    # Overlay confirmed daily BOS: forward-fill its sign from BrokenIndex.
    try:
        shl_d = smc.swing_highs_lows(daily, swing_length=cfg.swing_length)
        bos_d = smc.bos_choch(daily, swing_highs_lows=shl_d,
                              close_break=cfg.close_break)
        bos_sign = np.zeros(len(daily))
        bcol = bos_d["BOS"].values
        broken = bos_d["BrokenIndex"].values
        for i in range(len(daily)):
            v = bcol[i]
            if not np.isnan(v):
                bi = broken[i]
                if not np.isnan(bi):
                    bi = int(bi)
                    if 0 <= bi < len(daily):
                        bos_sign[bi] = v  # BOS known only at the break bar
        # forward-fill last non-zero BOS sign
        last = 0
        for i in range(len(daily)):
            if bos_sign[i] != 0:
                last = int(bos_sign[i])
            if last != 0:
                bias.iloc[i] = last
    except Exception:
        pass  # keep slope fallback
    return bias


def _bias_at(bias: pd.Series, ts: pd.Timestamp) -> int:
    """Bias in force at time ``ts`` (most recent daily bar at/before ts)."""
    prior = bias.loc[:ts]
    if len(prior) == 0:
        return 0
    return int(prior.iloc[-1])


def _select_bias(df5m: pd.DataFrame, cfg) -> pd.Series:
    """Daily-indexed bias series selected by ``cfg.bias_mode`` (+ 4H confluence).

    Iteration-3 default is mode ``C`` (draw-on-liquidity). Delegates to
    ``bias.compute_bias_modes`` and returns the key
    ``bias_mode + ("+4h" if use_4h_confluence else "")``. Imported lazily to
    avoid a circular import (bias.py imports from strategy.py).
    """
    from .bias import compute_bias_modes
    key = cfg.bias_mode + ("+4h" if cfg.use_4h_confluence else "")
    return compute_bias_modes(df5m, cfg)[key]


# --------------------------------------------------------------------------- #
# Sweep + BOS + zone detection on the 15m frame
# --------------------------------------------------------------------------- #
def _detect_sweeps(ohlc: pd.DataFrame, shl: pd.DataFrame, cfg) -> List[dict]:
    """Return list of sweep events: pierce of a pivot + body close-back.

    Each event dict: {bar, direction, level, extreme, pivot_bar}
      direction +1 = bullish sweep (swept a LOW / sell-side liquidity,
                     expecting up move); -1 = bearish (swept a HIGH).
      extreme = the wick extreme that pierced (used for SL).
    Anchored at the CLOSE-BACK bar (the completion bar), which is always
    >= pivot_bar + swing_length.
    """
    n = len(ohlc)
    high = ohlc["high"].values
    low = ohlc["low"].values
    close = ohlc["close"].values
    hl = shl["HighLow"].values
    lvl = shl["Level"].values

    # collect confirmed pivots with the bar they become KNOWN.
    pivots = []  # (pivot_bar, kind(+1 high/-1 low), level)
    for i in range(n):
        if not np.isnan(hl[i]):
            pivots.append((i, int(hl[i]), lvl[i]))

    events = []
    for pivot_bar, kind, level in pivots:
        known_bar = pivot_bar + cfg.swing_length  # earliest bar pivot is confirmed
        # scan forward for a pierce + close-back within window
        start = max(known_bar, pivot_bar + 1)
        for j in range(start, n):
            if kind == 1:  # swing HIGH -> look for a wick above it (buy-side liq)
                if high[j] > level:  # pierced
                    # close back BELOW level within window
                    for k in range(j, min(j + cfg.sweep_close_back_bars + 1, n)):
                        if close[k] < level:
                            events.append(dict(bar=k, direction=-1, level=level,
                                               extreme=float(np.max(high[j:k + 1])),
                                               pivot_bar=pivot_bar))
                            break
                    break  # first pierce of this pivot only
            else:  # swing LOW -> wick below it (sell-side liq)
                if low[j] < level:
                    for k in range(j, min(j + cfg.sweep_close_back_bars + 1, n)):
                        if close[k] > level:
                            events.append(dict(bar=k, direction=1, level=level,
                                               extreme=float(np.min(low[j:k + 1])),
                                               pivot_bar=pivot_bar))
                            break
                    break
    return events


def _find_bos_after(bos: pd.DataFrame, sweep_bar: int, direction: int,
                    n: int) -> Optional[int]:
    """First same-direction body-close structure break completing AT or
    AFTER ``sweep_bar``. Returns the ``BrokenIndex`` bar.

    Confirmation = BOS **or** CHOCH. TJR's post-sweep confirmation is an
    MSS: after a liquidity sweep prints a lower-low (bullish case), the
    body-close reclaim of the prior swing high is, in SMC terms, a bullish
    Change-of-Character (CHoCH), not a BOS (BOS requires a higher-low).
    Both are body-close breaks (``close_break=True``), so we accept either.
    ``BrokenIndex`` is the bar whose close broke the level -- the causal
    completion bar, always strictly after the swing it breaks.
    """
    bcol = bos["BOS"].values
    ccol = bos["CHOCH"].values
    broken = bos["BrokenIndex"].values
    best = None
    for i in range(n):
        v = bcol[i]
        if np.isnan(v):
            v = ccol[i]
        if np.isnan(v) or int(v) != direction:
            continue
        bi = broken[i]
        if np.isnan(bi):
            continue
        bi = int(bi)
        if bi >= sweep_bar:
            if best is None or bi < best:
                best = bi
    return best


def _precompute_breaks(bos: pd.DataFrame, n: int) -> "dict[int, np.ndarray]":
    """Sorted ``BrokenIndex`` bars per direction (+1/-1), computed ONCE.

    Same event definition as ``_find_bos_after`` (BOS or, if absent, CHOCH;
    anchored at the causal ``BrokenIndex`` completion bar) but hoisted out of
    the per-sweep loop so lookups become a binary search instead of a full
    O(n) rescan on every candidate. Returns ``{+1: sorted_bars, -1: ...}``.
    """
    bcol = bos["BOS"].values
    ccol = bos["CHOCH"].values
    broken = bos["BrokenIndex"].values
    ups: List[int] = []
    dns: List[int] = []
    for i in range(n):
        v = bcol[i]
        if np.isnan(v):
            v = ccol[i]
        if np.isnan(v) or int(v) == 0:
            continue
        bi = broken[i]
        if np.isnan(bi):
            continue
        bi = int(bi)
        (ups if int(v) == 1 else dns).append(bi)
    return {1: np.array(sorted(ups), dtype=int),
            -1: np.array(sorted(dns), dtype=int)}


def _bos_after_fast(breaks: "dict[int, np.ndarray]", sweep_bar: int,
                    direction: int) -> Optional[int]:
    """Smallest precomputed ``BrokenIndex >= sweep_bar`` for ``direction``.

    Equivalent to ``_find_bos_after`` (returns the earliest same-direction
    break completing at/after the sweep) via binary search on the sorted
    per-direction bars.
    """
    arr = breaks.get(direction)
    if arr is None or arr.size == 0:
        return None
    pos = int(np.searchsorted(arr, sweep_bar, side="left"))
    if pos >= arr.size:
        return None
    return int(arr[pos])


def _zone_from_displacement(fvg: pd.DataFrame, ob: pd.DataFrame,
                            bos_bar: int, direction: int, n: int):
    """Entry edge from the most-recent same-direction FVG/OB, causally safe.

    Known-bar lag (critical, look-ahead safety):
      * An FVG at positional bar ``i`` needs the THIRD candle (``i+1``) to
        exist, so it is only *known* at bar ``i+1``.
      * An OB is derived from swings and is treated as known at its own
        bar ``i`` (smc anchors OB at the order-block candle, mitigated
        later); we still require ``i <= bos_bar``.
    A zone may only be used if its known-bar is ``<= bos_bar`` -- i.e. it
    was fully formed no later than the confirming break bar. Entry (a
    limit the market must RETURN into) is the zone Top for a long, Bottom
    for a short.

    Returns ``(entry_price, kind, known_bar)`` or ``(None, None, None)``.
    """
    fcol = fvg["FVG"].values
    ftop = fvg["Top"].values
    fbot = fvg["Bottom"].values
    ocol = ob["OB"].values
    otop = ob["Top"].values
    obot = ob["Bottom"].values

    best = None  # (known_bar, price, kind)
    for i in range(0, min(bos_bar + 1, n)):
        # FVG known only at i+1
        if i + 1 <= bos_bar and not np.isnan(fcol[i]) and int(fcol[i]) == direction:
            price = ftop[i] if direction == 1 else fbot[i]
            if not np.isnan(price):
                known = i + 1
                if best is None or known > best[0]:
                    best = (known, float(price), "fvg")
        # OB known at i
        if not np.isnan(ocol[i]) and int(ocol[i]) == direction:
            price = otop[i] if direction == 1 else obot[i]
            if not np.isnan(price):
                if best is None or i > best[0]:
                    best = (i, float(price), "ob")
    if best is None:
        return None, None, None
    return best[1], best[2], best[0]


def _opposite_liquidity_tp(shl: pd.DataFrame, setup: pd.DataFrame,
                           bos_bar: int, direction: int, entry: float,
                           cfg, prev_high: "np.ndarray" = None,
                           prev_low: "np.ndarray" = None) -> Optional[float]:
    """Nearest OPPOSING liquidity level beyond ``entry``, causally selected.

    For a long: the nearest 15m swing-HIGH ``Level`` (from ``shl``) strictly
    above ``entry`` whose pivot bar became *confirmed* at/before ``bos_bar``
    (i.e. ``pivot_bar + swing_length <= bos_bar``), also considering the
    prior-day high from ``smc.previous_high_low`` in force at the confirming
    bar. Pick the CLOSEST such level above entry. Mirror for a short (nearest
    swing-LOW / prior-day-low strictly below). Returns the level price, or
    ``None`` if no valid opposing level exists.

    Causality: swing pivots are only knowable ``swing_length`` bars after the
    pivot, so we require ``pivot_bar + swing_length <= bos_bar``. The
    prior-day-high/low series is anchored per 15m bar; we read its value at
    the confirming ``bos_bar`` (which is <= the fill anchor), so no future
    bar informs the TP.
    """
    hl = np.asarray(shl["HighLow"].values, dtype=float)
    lvl = np.asarray(shl["Level"].values, dtype=float)
    n = len(hl)
    SL = cfg.swing_length

    # opposing swing levels (vectorized): for a long target swing HIGHS
    # (kind +1); for a short target swing LOWS (kind -1). A pivot at bar p is
    # confirmed only once p + SL <= bos_bar, and must be beyond entry.
    want_kind = 1 if direction == 1 else -1
    bars = np.arange(n)
    mask = (hl == want_kind) & (bars + SL <= bos_bar) & ~np.isnan(lvl)
    if direction == 1:
        mask &= lvl > entry
    else:
        mask &= lvl < entry
    candidates = [float(x) for x in lvl[mask]]

    # prior-day high/low pool in force at the confirming 15m bar (causal).
    # ``prev_high``/``prev_low`` are the ``smc.previous_high_low`` columns,
    # precomputed ONCE by the caller (they are O(bars) to build, so passing
    # them in avoids recomputing per candidate). Fall back to computing here
    # only when not supplied (e.g. direct unit tests).
    ph = prev_high
    pl = prev_low
    if ph is None or pl is None:
        try:
            phl = smc.previous_high_low(setup, time_frame="1D")
            ph = phl["PreviousHigh"].values if "PreviousHigh" in phl.columns else None
            pl = phl["PreviousLow"].values if "PreviousLow" in phl.columns else None
        except Exception:
            ph = pl = None
    col_arr = ph if direction == 1 else pl
    if col_arr is not None and 0 <= bos_bar < len(col_arr):
        pd_level = col_arr[bos_bar]
        if not np.isnan(pd_level):
            pd_level = float(pd_level)
            if direction == 1 and pd_level > entry:
                candidates.append(pd_level)
            elif direction == -1 and pd_level < entry:
                candidates.append(pd_level)

    if not candidates:
        return None
    # nearest to entry (closest opposing level beyond entry).
    if direction == 1:
        return min(candidates)     # smallest high above entry
    return max(candidates)         # largest low below entry


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def find_trades(df5m: pd.DataFrame, cfg) -> List[Trade]:
    """Detect all bias-aligned TJR 4X trades in ``df5m`` (5m OHLCV).

    Causal guarantee: every returned Trade is *created* using only bars
    up to its confirming BOS bar. ``entry_time`` is the first 5m bar
    strictly after the confirming 15m bar's close, so the engine resolves
    fills and SL/TP purely forward.
    """
    df5m = _prep(df5m)
    if len(df5m) < 50:
        return []

    bias = _select_bias(df5m, cfg)
    setup = _resample(df5m, cfg.setup_timeframe)
    if len(setup) < cfg.swing_length * 3:
        return []

    ohlc = setup.reset_index(drop=True)  # positional index for smc
    n = len(ohlc)
    shl = smc.swing_highs_lows(ohlc, swing_length=cfg.swing_length)
    bos = smc.bos_choch(ohlc, swing_highs_lows=shl, close_break=cfg.close_break)
    fvg = smc.fvg(ohlc)
    ob = smc.ob(ohlc, swing_highs_lows=shl)

    # Prior-day high/low pools for the opposite-liquidity TP, computed ONCE
    # (per-candidate recompute is quadratic). Only needed for that exit model.
    prev_high = prev_low = None
    if cfg.exit_model == "opposite_liquidity":
        try:
            phl = smc.previous_high_low(setup, time_frame="1D")
            if "PreviousHigh" in phl.columns:
                prev_high = phl["PreviousHigh"].values
            if "PreviousLow" in phl.columns:
                prev_low = phl["PreviousLow"].values
        except Exception:
            prev_high = prev_low = None

    sweeps = _detect_sweeps(ohlc, shl, cfg)
    breaks = _precompute_breaks(bos, n)  # per-direction sorted BrokenIndex bars
    setup_times = setup.index  # maps positional bar -> 15m bar start
    # duration of one setup bar (for close-time = next bar open, fill anchor)
    if len(setup_times) >= 2:
        tf_delta = setup_times[1] - setup_times[0]
    else:
        tf_delta = pd.Timedelta(minutes=15)

    trades: List[Trade] = []
    seen_bos = set()
    for ev in sweeps:
        direction = ev["direction"]
        sweep_bar = ev["bar"]

        bos_bar = _bos_after_fast(breaks, sweep_bar, direction)
        if bos_bar is None:
            continue
        # causality: BOS must confirm at/after pivot became known
        if bos_bar < ev["pivot_bar"] + cfg.swing_length:
            continue
        if bos_bar in seen_bos:
            continue

        # bias alignment as of the confirming 15m bar. When
        # ``cfg.apply_bias_filter`` is False, emit ALL directional
        # candidates (both long & short) so an external ablation can filter
        # per bias mode; no other behavior changes.
        confirm_bar_start = setup_times[bos_bar]
        confirm_bar_close = confirm_bar_start + tf_delta
        if cfg.apply_bias_filter:
            b = _bias_at(bias, confirm_bar_start)
            if b != direction:
                continue

        entry, kind, zone_known_bar = _zone_from_displacement(
            fvg, ob, bos_bar, direction, n)
        if entry is None:
            continue

        # The trade is only fully known once BOTH the confirming break and
        # the entry zone have formed. Anchor the fill window to the close of
        # the LATER of the two bars (both are <= bos_bar by construction, so
        # this is confirm_bar_close, but keep it explicit for safety).
        anchor_bar = max(bos_bar, zone_known_bar)
        anchor_close = setup_times[anchor_bar] + tf_delta

        # SL beyond the sweep extreme +/- buffer.
        extreme = ev["extreme"]
        if direction == 1:
            sl = extreme * (1 - cfg.sl_buffer_pct)
            risk = entry - sl
        else:
            sl = extreme * (1 + cfg.sl_buffer_pct)
            risk = sl - entry
        if risk <= 0:
            continue

        # Min-stop filter: skip setups whose stop is a tiny fraction of price
        # (their fee-per-R cost tax is disproportionate). 0 = off.
        if cfg.min_stop_pct > 0 and (risk / entry) < cfg.min_stop_pct:
            continue

        # TP: fixed RR, or the nearest opposing liquidity level (causal).
        if cfg.exit_model == "opposite_liquidity":
            tp = _opposite_liquidity_tp(shl, setup, bos_bar, direction,
                                        entry, cfg, prev_high, prev_low)
            if tp is None:
                continue
            rr = (tp - entry) / risk if direction == 1 else (entry - tp) / risk
            if rr < cfg.min_rr:
                continue
        else:  # fixed_rr
            if direction == 1:
                tp = entry + cfg.rr_target * risk
            else:
                tp = entry - cfg.rr_target * risk

        # entry eligible from the first 5m bar AFTER the anchor bar closes
        trades.append(Trade(
            entry_time=anchor_close,
            direction=direction,
            entry=float(entry),
            sl=float(sl),
            tp=float(tp),
            sweep_level=float(ev["level"]),
            bos_index=int(bos_bar),
            confirm_time=anchor_close,
        ))
        seen_bos.add(bos_bar)

    trades.sort(key=lambda t: t.entry_time)
    return trades
