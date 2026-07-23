"""Daily-bias determination engines for the TJR-4X backtester ablation.

Every engine returns a **daily-indexed** ``pd.Series`` in {+1, -1, 0}
(bullish / bearish / flat). All engines are **strictly causal**: the value
in force at day D uses only bars whose close is at or before day D's close.
This is enforced two ways:

  * Swings (``smc.swing_highs_lows``) with ``swing_length=SL`` are only
    *knowable* ``SL`` bars after the pivot; when we need a confirmed swing
    "as of day D" we only accept pivots at bar ``p`` with ``p + SL <= D``.
  * Structure breaks (``smc.bos_choch``) carry the break sign, but the
    break is only *confirmed* at its ``BrokenIndex`` bar -- never at the
    pivot bar. We anchor every break's sign at ``BrokenIndex`` and
    forward-fill, so no future bar can influence an earlier day.

Encodings (see ``docs/research/BIAS_METHOD.md``):
  A  structure-only          -- sign of last confirmed daily break.
  B  A + premium/discount    -- neutralize when price is on the wrong side
                                of the current dealing-range equilibrium.
  C  A + draw-on-liquidity    -- keep the sign only if it points toward the
                                nearest unswept opposing daily pool.
  4H confluence              -- 4H last-confirmed-break sign, daily as-of.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from smartmoneyconcepts import smc

from .strategy import _resample, compute_bias, _bias_at


# --------------------------------------------------------------------------- #
# Shared: last-confirmed-break sign, causally anchored at BrokenIndex.
# --------------------------------------------------------------------------- #
def _last_break_sign(ohlc: pd.DataFrame, swing_length: int) -> np.ndarray:
    """Positional array of the last confirmed break sign per bar (0 before
    the first break). CHoCH takes precedence over BOS at the same event bar.

    Causality: a break detected at event bar ``i`` has its sign applied only
    from ``BrokenIndex[i]`` onward (the bar whose close actually broke the
    level), then forward-filled. ``BrokenIndex`` is always strictly after the
    swing it breaks, so no future bar sets an earlier day's value.
    """
    n = len(ohlc)
    out = np.zeros(n, dtype=int)
    if n < 2:
        return out
    shl = smc.swing_highs_lows(ohlc, swing_length=swing_length)
    bc = smc.bos_choch(ohlc, swing_highs_lows=shl, close_break=True)
    bos = bc["BOS"].values
    choch = bc["CHOCH"].values
    broken = bc["BrokenIndex"].values

    # struct = CHOCH where present else BOS (CHoCH precedence, reversal-first)
    anchored = np.zeros(n, dtype=float)
    for i in range(n):
        v = choch[i]
        if np.isnan(v):
            v = bos[i]
        if np.isnan(v) or int(v) == 0:
            continue
        bi = broken[i]
        if np.isnan(bi):
            continue
        bi = int(bi)
        if 0 <= bi < n:
            anchored[bi] = int(v)  # sign known only at the break/confirm bar

    last = 0
    for i in range(n):
        if anchored[i] != 0:
            last = int(anchored[i])
        out[i] = last
    return out


# --------------------------------------------------------------------------- #
# Encoding A -- structure-only
# --------------------------------------------------------------------------- #
def bias_structure(daily: pd.DataFrame, cfg) -> pd.Series:
    """Encoding A: sign of the last confirmed daily BOS/CHoCH, ffilled.

    +1 if the last confirmed daily break was up, -1 if down, 0 before the
    first confirmed break.
    """
    ohlc = daily.reset_index(drop=True)
    signs = _last_break_sign(ohlc, cfg.swing_length)
    return pd.Series(signs, index=daily.index, dtype=int)


# --------------------------------------------------------------------------- #
# Encoding B -- structure + premium/discount gate
# --------------------------------------------------------------------------- #
def bias_premium_discount(df5m: pd.DataFrame, daily: pd.DataFrame, cfg) -> pd.Series:
    """Encoding B: Encoding A, neutralized when price is on the wrong side
    of the current daily dealing-range equilibrium.

    Equilibrium = 50% of the current daily dealing range = midpoint of the
    last *confirmed* daily swing high and swing low as of day D (from
    ``smc.swing_highs_lows``). A swing at pivot bar ``p`` counts as confirmed
    only once ``p + swing_length <= D`` (pivot-confirmation lag), so eq at
    day D never peeks at a future swing.

    Keep +1 only if close < eq (discount); keep -1 only if close > eq
    (premium); else 0.

    NOTE: This pins the equilibrium reference to the last-confirmed swing
    high/low pair, which resolves the "#1 gap" (which swing defines the
    range) from BIAS_METHOD.md -- *for the backtest only*.
    """
    base = bias_structure(daily, cfg).values.copy()
    ohlc = daily.reset_index(drop=True)
    n = len(ohlc)
    close = ohlc["close"].values
    SL = cfg.swing_length

    shl = smc.swing_highs_lows(ohlc, swing_length=SL)
    hl = shl["HighLow"].values
    lvl = shl["Level"].values

    # last confirmed swing HIGH level and swing LOW level as of each bar D.
    last_high = np.full(n, np.nan)
    last_low = np.full(n, np.nan)
    ch = cl = np.nan
    for D in range(n):
        # promote any pivot that has just become confirmed at bar D
        p = D - SL  # a pivot at p is confirmed at p + SL == D
        if 0 <= p < n and not np.isnan(hl[p]):
            if int(hl[p]) == 1:
                ch = lvl[p]
            elif int(hl[p]) == -1:
                cl = lvl[p]
        last_high[D] = ch
        last_low[D] = cl

    out = base.copy()
    for D in range(n):
        if base[D] == 0:
            continue
        hi, lo = last_high[D], last_low[D]
        if np.isnan(hi) or np.isnan(lo):
            out[D] = 0  # no confirmed range yet -> stand down
            continue
        eq = (hi + lo) / 2.0
        c = close[D]
        if base[D] == 1 and c < eq:       # bullish + discount -> keep
            out[D] = 1
        elif base[D] == -1 and c > eq:    # bearish + premium -> keep
            out[D] = -1
        else:
            out[D] = 0                    # right dir, wrong half -> stand down
    return pd.Series(out.astype(int), index=daily.index, dtype=int)


# --------------------------------------------------------------------------- #
# Encoding C -- draw-on-liquidity, structure-gated
# --------------------------------------------------------------------------- #
def bias_draw_liquidity(df5m: pd.DataFrame, daily: pd.DataFrame, cfg) -> pd.Series:
    """Encoding C: Encoding A, kept only if the sign points toward the
    nearest *unswept* opposing daily liquidity pool.

    Pools: on a frame that is already daily, ``smc.previous_high_low(daily,
    '1D')`` degenerates to all-NaN (there are no sub-daily bars to aggregate
    into a "previous period"), so we use the design-doc-sanctioned fallback
    of prior-day highs/lows -- the nearest *unswept* prior-day extreme on
    each side. As of day D we build the running set of prior-day highs above
    the close (unswept buy-side pools) and prior-day lows below the close
    (unswept sell-side pools) from days strictly < D, so it is causal by
    construction. "Unswept" = the pool's high has not since been exceeded /
    the pool's low not since undercut by any intervening day.

    Bullish kept if the nearest unswept pool is above current price, bearish
    if below; else 0.
    """
    base = bias_structure(daily, cfg).values.copy()
    ohlc = daily.reset_index(drop=True)
    n = len(ohlc)
    close = ohlc["close"].values
    high = ohlc["high"].values
    low = ohlc["low"].values

    out = base.copy()
    for D in range(n):
        if base[D] == 0:
            continue
        c = close[D]
        # nearest UNSWEPT prior-day high strictly above c: a prior high h at
        # day p<D is unswept iff no day in (p, D) printed a high >= h. The
        # nearest such pool above c is simply the smallest prior-day high that
        # is still > c AND has not been exceeded since it printed.
        nearest_up = np.inf
        nearest_dn = np.inf
        for p in range(D - 1, -1, -1):
            hp = high[p]
            if hp > c and not np.isfinite(nearest_up):
                # unswept iff nothing between p and D exceeded it
                if not (high[p + 1:D + 1] >= hp).any():
                    nearest_up = hp - c
            lp = low[p]
            if lp < c and not np.isfinite(nearest_dn):
                if not (low[p + 1:D + 1] <= lp).any():
                    nearest_dn = c - lp
            if np.isfinite(nearest_up) and np.isfinite(nearest_dn):
                break
        if not np.isfinite(nearest_up) and not np.isfinite(nearest_dn):
            out[D] = 0
            continue
        dir_to_draw = 1 if nearest_up <= nearest_dn else -1
        out[D] = base[D] if dir_to_draw == base[D] else 0
    return pd.Series(out.astype(int), index=daily.index, dtype=int)


# --------------------------------------------------------------------------- #
# 4H confluence
# --------------------------------------------------------------------------- #
def confluence_4h(df5m: pd.DataFrame, cfg) -> pd.Series:
    """4H last-confirmed-break sign (Encoding-A logic on the 4H frame),
    reindexed to the daily index via as-of (value in force at each day's
    start, using only 4H bars closed by then).
    """
    h4 = _resample(df5m, cfg.confluence_timeframe)
    daily = _resample(df5m, cfg.bias_timeframe)
    if len(h4) < 2:
        return pd.Series(0, index=daily.index, dtype=int)
    signs = _last_break_sign(h4.reset_index(drop=True), cfg.swing_length)
    s4 = pd.Series(signs, index=h4.index, dtype=int)
    # as-of: for each daily bar start, the last 4H value at/before it.
    out = s4.reindex(s4.index.union(daily.index)).ffill().reindex(daily.index)
    return out.fillna(0).astype(int)


# --------------------------------------------------------------------------- #
# Mode dispatcher
# --------------------------------------------------------------------------- #
def _apply_4h_gate(base: pd.Series, conf: pd.Series) -> pd.Series:
    """Zero the base bias on days where the 4H sign OPPOSES it. Agreement or
    a neutral 4H (0) passes through unchanged.
    """
    b = base.values
    c = conf.reindex(base.index).fillna(0).values
    out = b.copy()
    for i in range(len(b)):
        if b[i] != 0 and c[i] != 0 and c[i] != b[i]:
            out[i] = 0
    return pd.Series(out.astype(int), index=base.index, dtype=int)


def compute_bias_modes(df5m: pd.DataFrame, cfg) -> "dict[str, pd.Series]":
    """Return every daily-indexed bias series for the ablation.

    Keys: ``current`` (existing compute_bias), ``A``, ``B``, ``C``,
    ``A+4h``, ``B+4h``, ``C+4h``. For ``*+4h`` the base bias is zeroed on
    days where the 4H sign opposes it (agreement or 4H-neutral passes).
    """
    from .strategy import _prep
    df5m = _prep(df5m)
    daily = _resample(df5m, cfg.bias_timeframe)

    current = compute_bias(df5m, cfg)
    A = bias_structure(daily, cfg)
    B = bias_premium_discount(df5m, daily, cfg)
    C = bias_draw_liquidity(df5m, daily, cfg)
    conf = confluence_4h(df5m, cfg)

    return {
        "current": current,
        "A": A,
        "B": B,
        "C": C,
        "A+4h": _apply_4h_gate(A, conf),
        "B+4h": _apply_4h_gate(B, conf),
        "C+4h": _apply_4h_gate(C, conf),
    }
