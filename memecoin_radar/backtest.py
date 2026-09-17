"""Outcome labelling and threshold evaluation, PRD section 8.

The thresholds in `config.py` are guesses. This module is how they stop being
guesses: it labels what actually happened to every recorded launch, then reports
precision, recall, and rug rate for the alerts that fired.

Read the verdict honestly. `evaluate` reports the base rate alongside every
precision figure, because a tier that alerts on 40% of launches and catches 40%
of the winners has found nothing at all. The comparison that matters is alert
precision against base rate, not precision on its own.

Snapshot coverage note: the live collector snapshots to one hour. The 6h/24h/7d
windows only exist for tokens that `refresh` has re-polled later, so those
columns stay NULL until that has run. A missing window is reported as missing,
never as zero return.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import load_config
from .sources.dexscreener import DexScreenerClient
from .store import Store

log = logging.getLogger("backtest")

RETURN_WINDOWS: dict[str, float] = {
    "max_return_1h": 3600.0,
    "max_return_6h": 21_600.0,
    "max_return_24h": 86_400.0,
    "max_return_7d": 604_800.0,
}

MULTIPLES: dict[str, float] = {
    "t_2x": 2.0,
    "t_5x": 5.0,
    "t_10x": 10.0,
    "t_20x": 20.0,
    "t_50x": 50.0,
    "t_100x": 100.0,
}

# A token whose liquidity or market cap collapses to near nothing is treated as
# rugged. This is an outcome label, not an accusation of intent: the PRD needs
# to know the position became unexitable, not why.
RUG_COLLAPSE_RATIO = 0.15


@dataclass
class Outcome:
    mint: str
    entry_mcap_usd: float
    returns: dict[str, float | None]
    max_drawdown: float
    rugged: bool
    times_to_multiple: dict[str, float | None]


def label_one(snapshots: list[dict]) -> Outcome | None:
    """Label one token from its snapshot series.

    Entry is the first snapshot with a positive market cap, which is the earliest
    point the radar could have alerted. Using the launch event's curve price
    instead would credit the strategy with a fill nobody could have gotten.
    """
    usable = [s for s in snapshots if (s.get("market_cap_usd") or 0) > 0]
    if len(usable) < 2:
        return None

    entry = usable[0]
    entry_mcap = float(entry["market_cap_usd"])
    mint = str(entry["mint"])

    returns: dict[str, float | None] = {}
    for field, window in RETURN_WINDOWS.items():
        in_window = [s for s in usable if float(s["age_seconds"]) <= window]
        # Distinguish "no data yet for this window" from "no gain in this window".
        covered = any(float(s["age_seconds"]) >= window * 0.8 for s in usable)
        if len(in_window) < 2 or not covered:
            returns[field] = None
            continue
        peak = max(float(s["market_cap_usd"]) for s in in_window)
        returns[field] = peak / entry_mcap - 1.0

    peak_so_far = entry_mcap
    max_dd = 0.0
    for snap in usable:
        mcap = float(snap["market_cap_usd"])
        peak_so_far = max(peak_so_far, mcap)
        max_dd = min(max_dd, mcap / peak_so_far - 1.0)

    last = usable[-1]
    peak_all = max(float(s["market_cap_usd"]) for s in usable)
    rugged = (
        float(last["market_cap_usd"]) <= peak_all * RUG_COLLAPSE_RATIO
        or (float(last.get("liquidity_usd") or 0) <= 0 and float(entry.get("liquidity_usd") or 0) > 0)
    )

    times: dict[str, float | None] = {}
    for field, multiple in MULTIPLES.items():
        hit = next(
            (float(s["age_seconds"]) for s in usable
             if float(s["market_cap_usd"]) >= entry_mcap * multiple),
            None,
        )
        times[field] = hit

    return Outcome(
        mint=mint,
        entry_mcap_usd=entry_mcap,
        returns=returns,
        max_drawdown=max_dd,
        rugged=rugged,
        times_to_multiple=times,
    )


def label_all(store: Store, *, min_age_seconds: float = 3600.0) -> int:
    """Label every token old enough to have a settled outcome. Returns the count."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=min_age_seconds)).isoformat()
    rows = store.conn.execute(
        "SELECT mint FROM tokens WHERE created_at <= ? ORDER BY created_at", (cutoff,)
    ).fetchall()

    labeled = 0
    for row in rows:
        mint = row["mint"]
        outcome = label_one(store.snapshots_for(mint))
        if outcome is None:
            continue
        with store.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO outcomes
                   (mint, labeled_at, entry_mcap_usd, max_return_1h, max_return_6h,
                    max_return_24h, max_return_7d, max_drawdown, rugged,
                    t_2x, t_5x, t_10x, t_20x, t_50x, t_100x)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    outcome.mint,
                    datetime.now(timezone.utc).isoformat(),
                    outcome.entry_mcap_usd,
                    outcome.returns["max_return_1h"],
                    outcome.returns["max_return_6h"],
                    outcome.returns["max_return_24h"],
                    outcome.returns["max_return_7d"],
                    outcome.max_drawdown,
                    int(outcome.rugged),
                    outcome.times_to_multiple["t_2x"],
                    outcome.times_to_multiple["t_5x"],
                    outcome.times_to_multiple["t_10x"],
                    outcome.times_to_multiple["t_20x"],
                    outcome.times_to_multiple["t_50x"],
                    outcome.times_to_multiple["t_100x"],
                ),
            )
        labeled += 1
    return labeled


def evaluate(store: Store, *, winner_multiple: float = 10.0) -> dict:
    """Compare what alerted against what actually ran.

    Every precision number is reported next to the base rate it must beat.
    """
    rows = store.conn.execute(
        """SELECT o.mint, o.entry_mcap_usd, o.max_return_1h, o.rugged, o.t_10x, o.t_2x
           FROM outcomes o"""
    ).fetchall()
    if not rows:
        return {"error": "no labelled outcomes yet; run `label` after collecting"}

    def is_winner(row) -> bool:
        return row["t_10x"] is not None if winner_multiple == 10.0 else False

    total = len(rows)
    winners = {r["mint"] for r in rows if is_winner(r)}
    rugs = {r["mint"] for r in rows if r["rugged"]}
    base_rate = len(winners) / total

    alert_rows = store.conn.execute(
        "SELECT mint, alert_type, ts FROM alerts ORDER BY ts"
    ).fetchall()
    by_tier: dict[str, set[str]] = {}
    first_alert_at: dict[str, str] = {}
    for row in alert_rows:
        by_tier.setdefault(row["alert_type"], set()).add(row["mint"])
        first_alert_at.setdefault(row["mint"], row["ts"])

    report: dict = {
        "tokens_labelled": total,
        "winner_multiple": winner_multiple,
        "winners": len(winners),
        "base_rate": round(base_rate, 5),
        "rug_rate_all": round(len(rugs) / total, 4),
        "tiers": {},
    }

    for tier, mints in sorted(by_tier.items()):
        scored = mints & {r["mint"] for r in rows}
        if not scored:
            continue
        hits = scored & winners
        tier_rugs = scored & rugs
        entry_caps = [
            float(r["entry_mcap_usd"]) for r in rows if r["mint"] in scored and r["entry_mcap_usd"]
        ]
        precision = len(hits) / len(scored)
        report["tiers"][tier] = {
            "alerted": len(scored),
            "winners_caught": len(hits),
            "precision": round(precision, 4),
            "lift_vs_base_rate": round(precision / base_rate, 2) if base_rate else None,
            "recall_of_all_winners": round(len(hits) / len(winners), 4) if winners else None,
            "rug_rate": round(len(tier_rugs) / len(scored), 4),
            "median_entry_mcap_usd": round(statistics.median(entry_caps), 0) if entry_caps else None,
        }

    report["verdict"] = _verdict(report)
    return report


def _verdict(report: dict) -> str:
    """State plainly whether the alerts beat doing nothing."""
    tiers = report.get("tiers") or {}
    loud = {t: v for t, v in tiers.items() if t in ("HOT", "ULTRA", "TREND_ECHO")}
    if not loud:
        return "No loud alerts have fired yet. Nothing to judge."
    best = max(loud.values(), key=lambda v: v.get("lift_vs_base_rate") or 0)
    lift = best.get("lift_vs_base_rate")
    if lift is None:
        return "Base rate is zero, so lift is undefined. Collect more data."
    if best["alerted"] < 30:
        return (
            f"Only {best['alerted']} alerts in the best tier. Too few to conclude anything; "
            "treat any lift as noise until the count is well past 30."
        )
    if lift < 1.2:
        return f"Best tier lift is {lift}x base rate. The filters are not earning their place."
    return f"Best tier lift is {lift}x base rate over {best['alerted']} alerts."


async def refresh(store: Store, *, max_age_hours: float = 168.0) -> int:
    """Re-poll older tokens so the 6h/24h/7d windows can be labelled.

    Run this on a schedule. Without it the long-horizon outcome columns stay
    NULL forever, and the PRD's 10x/100x recall metrics cannot be computed.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    rows = store.conn.execute(
        "SELECT mint, created_at FROM tokens WHERE created_at >= ? ORDER BY created_at DESC",
        (cutoff,),
    ).fetchall()
    if not rows:
        return 0

    updated = 0
    async with DexScreenerClient() as dex:
        mints = [r["mint"] for r in rows]
        for i in range(0, len(mints), 30):
            chunk = mints[i : i + 30]
            states = await dex.token_states(chunk)
            created = {r["mint"]: r["created_at"] for r in rows}
            for mint, state in states.items():
                age = (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(created[mint])
                ).total_seconds()
                from .models import MarketSnapshot, utcnow

                store.record_snapshot(
                    MarketSnapshot(
                        mint=mint,
                        ts=utcnow(),
                        age_seconds=round(age),
                        price_usd=state.price_usd,
                        market_cap_usd=state.market_cap_usd,
                        liquidity_usd=state.liquidity_usd,
                        volume_usd=state.volume_h1_usd,
                        buys=state.buys_m5,
                        sells=state.sells_m5,
                        source="dexscreener-refresh",
                    )
                )
                updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Radar outcome labelling and evaluation")
    parser.add_argument("command", choices=["label", "evaluate", "refresh"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = load_config()
    store = Store(cfg.db_path)
    try:
        if args.command == "label":
            print(f"labelled {label_all(store)} tokens")
        elif args.command == "refresh":
            print(f"refreshed {asyncio.run(refresh(store))} tokens")
        else:
            print(json.dumps(evaluate(store), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
