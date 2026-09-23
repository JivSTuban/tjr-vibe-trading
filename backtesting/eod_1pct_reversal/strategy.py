"""Spec §3.2 hard gates + §7 incremental filter ladder — pure.

The ladder matters more than any single number. Spec §7 says to add one filter at a
time so each one's marginal contribution is visible. The sibling study
(`eod_pressure_reversal`) found its entire six-filter stack was worth +0.77 bps over
"buy any red name" — a fact invisible to anyone who only ran the final config. So the
control rung (`L0_all`, no gate but tradability) is built in from the start, not
bolted on after a good-looking result.
"""
from __future__ import annotations

import pandas as pd

from .features import DEFAULTS

# Spec §7 steps 1-8, cumulative. Each rung adds exactly one condition.
LADDER = [
    ("L0_all", []),                                   # control: any tradable name
    ("L1_prevlow", ["prevlow"]),                      # step 1: near previous-day low
    ("L2_red", ["prevlow", "red"]),                   # step 2: + current-day red
    ("L3_late", ["prevlow", "red", "late"]),          # step 3: + late-session pressure
    ("L4_cloc", ["prevlow", "red", "late", "cloc"]),  # step 4: + close location
    ("L5_range", ["prevlow", "red", "late", "cloc", "range"]),          # step 5
    ("L6_sector", ["prevlow", "red", "late", "cloc", "range", "sector"]),  # step 8
]

# Which ladder rung is the spec's own default configuration (§12). Sector-relative is
# marked "optional" in §3.2, so the shipped config is L5 plus sector as a variant.
SPEC_CONFIG = "L5_range"


def ladder_for(available: set[str]) -> list[tuple[str, list[str]]]:
    """The ladder with unmeasurable gates REMOVED from each rung, not the rung dropped.

    The daily path has no 15:30 mark, so `late` cannot be evaluated. Skipping every
    rung that mentions it would silently delete the spec's own configuration from the
    report — which is how this project has repeatedly shipped a signal nobody could
    see. Instead the gate is dropped and the rung is renamed with a `-late` suffix so
    the absence is visible in every row of the output table.
    """
    out = []
    for name, gates in LADDER:
        kept = [g for g in gates if g in available]
        if kept != gates:
            missing = [g for g in gates if g not in available]
            if not kept and gates:
                continue                      # the rung was ONLY the missing gate
            name = f"{name}-{'-'.join(missing)}"
        if out and out[-1][1] == kept:
            continue                          # rung adds nothing once the gate is gone
        out.append((name, kept))
    return out


def conditions(feats: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """Pure: one boolean column per spec gate.

    A gate whose feature is NaN evaluates False — it does NOT pass. On the daily path
    `late_return_pct` is always NaN, so `late` is False everywhere and any rung
    containing it would select nothing; `run.py` therefore drops the `late` rung on
    that path explicitly and says so, rather than letting a silent all-False column
    look like "no setups exist". That confusion is the house failure mode: a gate that
    cannot fire is indistinguishable from a quiet market.
    """
    p = {**DEFAULTS, **(params or {})}
    return pd.DataFrame(
        {
            "prevlow": (
                (feats["prev_low_distance_pct"] >= p["prev_low_distance_min_pct"])
                & (feats["prev_low_distance_pct"] <= p["prev_low_distance_max_pct"])
            ).fillna(False),
            "red": (feats["day_return_pct"] <= p["max_day_return_pct"]).fillna(False),
            "late": (feats["late_return_pct"] <= p["max_late_return_pct"]).fillna(False),
            "cloc": (feats["close_location_value"] <= p["max_close_location"]).fillna(False),
            "range": (feats["range_capacity_pct"] >= p["min_range_capacity_pct"]).fillna(False),
            "sector": (feats["sector_relative_pct"] <= p["max_sector_relative_pct"]).fillna(False),
        },
        index=feats.index,
    )


def rung_mask(conds: pd.DataFrame, gates: list[str]) -> pd.Series:
    """Pure: AND of the named gates. An empty list is the control (all True)."""
    if not gates:
        return pd.Series(True, index=conds.index)
    return conds[gates].all(axis=1)
