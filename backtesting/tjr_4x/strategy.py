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

    bias = compute_bias(df5m, cfg)
    setup = _resample(df5m, cfg.setup_timeframe)
    if len(setup) < cfg.swing_length * 3:
        return []

    ohlc = setup.reset_index(drop=True)  # positional index for smc
    n = len(ohlc)
    shl = smc.swing_highs_lows(ohlc, swing_length=cfg.swing_length)
    bos = smc.bos_choch(ohlc, swing_highs_lows=shl, close_break=cfg.close_break)
    fvg = smc.fvg(ohlc)
    ob = smc.ob(ohlc, swing_highs_lows=shl)

    sweeps = _detect_sweeps(ohlc, shl, cfg)
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

        bos_bar = _find_bos_after(bos, sweep_bar, direction, n)
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

        # SL beyond the sweep extreme +/- buffer; TP at fixed RR
        extreme = ev["extreme"]
        if direction == 1:
            sl = extreme * (1 - cfg.sl_buffer_pct)
            risk = entry - sl
            if risk <= 0:
                continue
            tp = entry + cfg.rr_target * risk
        else:
            sl = extreme * (1 + cfg.sl_buffer_pct)
            risk = sl - entry
            if risk <= 0:
                continue
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
