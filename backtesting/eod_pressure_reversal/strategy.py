"""Spec §9 staged build order + §6 top-5 selection + §7 exits. Pure, no network.

The staged build exists so we can see WHERE the edge comes from (or that it never
arrives). Each stage adds one filter to the previous one:

  0  any red stock                     5  + relative late volume >= 1.5x
  1  + DayReturn <= -1.5%              6  + no earnings in the hold window
  2  + late selling (close-location)   7  + rank, take top 5
  3  + drawdown from high <= -2%
  4  + sector-relative <= -1%

Stages 0-6 trade EVERY qualifying name equal-weighted (that is what makes them a
clean read on the filter's own contribution); only stage 7 imposes the 5-name cap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import signals

STAGE_FILTERS = {
    0: [],
    1: ["A_day"],
    2: ["A_day", "B_late"],
    3: ["A_day", "B_late", "C_high"],
    4: ["A_day", "B_late", "C_high", "D_sector"],
    5: ["A_day", "B_late", "C_high", "D_sector", "E_vol"],
    6: ["A_day", "B_late", "C_high", "D_sector", "E_vol"],   # + earnings, applied below
    7: ["A_day", "B_late", "C_high", "D_sector", "E_vol"],   # + earnings + top-5
}
STAGE_LABELS = {
    0: "any red stock",
    1: "+ day <= -1.5%",
    2: "+ late selling",
    3: "+ drawdown from high",
    4: "+ sector-relative",
    5: "+ late volume",
    6: "+ no earnings",
    7: "+ rank, top 5",
}


def build_candidates(
    features: dict[str, pd.DataFrame],
    thresholds: dict | None = None,
    min_price: float = 10.0,
    min_adv: float = 50e6,
    membership_mask: dict[str, pd.Series] | None = None,
    action_mask: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Pure: flatten per-ticker feature frames into one tidy candidate table.

    One row per (date, ticker) that is tradable that session, carrying every feature
    and every filter flag. ``action_mask`` marks corporate-action days to drop (spec
    §8) and ``membership_mask`` enforces point-in-time index membership.
    """
    parts = []
    for tkr, feats in features.items():
        ok = signals.liquid(feats, min_price, min_adv)
        if membership_mask is not None and tkr in membership_mask:
            ok &= membership_mask[tkr].reindex(feats.index).fillna(False)
        if action_mask is not None and tkr in action_mask:
            ok &= ~action_mask[tkr].reindex(feats.index).fillna(False)
        ok &= feats["next_open"].notna() & feats["day_ret"].notna() & feats["rel_vol"].notna()
        if not ok.any():
            continue
        sub = feats.loc[ok].copy()
        flags = signals.passes(sub, thresholds)
        sub = pd.concat([sub, flags], axis=1)
        sub["ticker"] = tkr
        parts.append(sub)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts).reset_index().rename(columns={"index": "date"})
    return out.sort_values(["date", "ticker"]).reset_index(drop=True)


def apply_stage(
    cands: pd.DataFrame,
    stage: int,
    blocked: set | None = None,
    top_n: int = 5,
) -> pd.DataFrame:
    """Pure: filter the candidate table down to the trades a given stage takes."""
    df = cands
    if stage == 0:
        df = df[df["day_ret"] < 0]                       # "any stock red today"
    else:
        for col in STAGE_FILTERS[stage]:
            df = df[df[col]]
    if stage >= 6 and blocked:
        keep = [(pd.Timestamp(d), t) not in blocked for d, t in zip(df["date"], df["ticker"])]
        df = df[pd.Series(keep, index=df.index)]
    df = df.copy()
    if stage >= 7:
        # Scored per day explicitly rather than via groupby.apply: apply's return
        # shape flips between Series and DataFrame depending on group count, which
        # silently breaks single-day slices.
        score = pd.Series(np.nan, index=df.index, dtype=float)
        for _, grp in df.groupby("date", sort=False):
            score.loc[grp.index] = signals.percentile_scores(grp[signals.FEATURES])
        df["score"] = score
        df = (
            df.sort_values(["date", "score"], ascending=[True, False])
              .groupby("date", group_keys=False)
              .head(top_n)
        )
    return df.reset_index(drop=True)


def simulate(trades: pd.DataFrame, cost_bps: float = 0.0, exit_col: str = "next_open") -> pd.DataFrame:
    """Pure: attach per-trade overnight returns net of round-trip costs.

    Entry is the signal-day close, exit is the next session's open (spec §7 variant A).
    ``cost_bps`` is charged PER SIDE, so a 5 bps setting costs 10 bps round trip.

    No stop is simulated, per spec §8: an overnight stop cannot be assumed to fill,
    and pretending it does is the single most common way an overnight backtest hides
    its left tail.
    """
    out = trades.copy()
    entry = out["price"].astype(float)
    exit_px = out[exit_col].astype(float)

    # Total return across the hold: prices are re-expressed on a common adjustment
    # basis so a split or dividend ex-date overnight is not read as a price move.
    # Falls back to raw prices when factors are absent (FMP-rescued tickers).
    f0 = out["adj_factor"].astype(float) if "adj_factor" in out else pd.Series(1.0, index=out.index)
    f1 = out["next_adj_factor"].astype(float) if "next_adj_factor" in out else pd.Series(1.0, index=out.index)
    f0 = f0.where(f0 > 0, 1.0).fillna(1.0)
    f1 = f1.where(f1 > 0, 1.0).fillna(1.0)

    gross = (exit_px * f1) / (entry * f0) - 1.0
    out["gross_ret"] = gross
    out["net_ret"] = gross - 2.0 * (cost_bps / 1e4)
    out["raw_gap"] = exit_px / entry - 1.0             # unadjusted, for diffing corp actions
    return out


def equity_curve(trades: pd.DataFrame, ret_col: str = "net_ret") -> pd.DataFrame:
    """Pure: equal-weighted daily portfolio return and its compounded curve.

    Equal weight ACROSS THAT DAY'S positions (spec §8), so a day with 2 signals is not
    silently 2.5x the risk of a day with 5. Days with no signal earn 0 (flat, in cash),
    which is what makes the exposure metric meaningful.
    """
    if trades.empty:
        return pd.DataFrame(columns=["date", "ret", "equity", "n"])
    daily = (
        trades.groupby("date")
        .agg(ret=(ret_col, "mean"), n=(ret_col, "size"))
        .sort_index()
        .reset_index()
    )
    daily["equity"] = (1.0 + daily["ret"]).cumprod()
    return daily
