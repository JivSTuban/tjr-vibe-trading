"""Which exit rule survives on a fat-tailed asset, measured rather than argued.

The question this answers: Jiv proposed "deploy $100, exit at +50%, repeat".
That is a fixed small take-profit with no stop, and on a positively-skewed
return distribution it is the one shape that reliably destroys the edge, because
the few enormous winners are the entire expectancy and a +50% cap truncates them
while the losers run to -90% unimpeded.

That is a claim, not a fact, so this measures it.

Data
----
`market_snapshots` from the sibling launch radar: every pump.fun launch it saw,
tracked forward on an 8-point ladder (15s, 30s, 60s, 3m, 5m, 10m, 30m, 1h).

Two properties of that table decide how this is written:

  * `price_usd` is 0 for pumpportal rows, but `market_cap_usd` is populated.
    Supply is fixed, so market cap is proportional to price and every RETURN is
    identical. The fill model is scale-free in price too (impact depends only on
    USD spend against the USD quote reserve, and the price cancels out of both
    legs), so market cap is a valid price series for costs as well.
  * Tracking stops at one hour. Any exit rule needing a longer horizon cannot be
    evaluated here, and is reported as such rather than silently truncated.

The honest caveat, stated once and applying to every number below: this is the
population of ALL launches, not the population the signal would select. The
absolute returns therefore do NOT transfer to the live strategy. What transfers
is the SHAPE: how a given exit rule interacts with a fat tail. That is the
question being asked.
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fomo_radar.fill import CostModel, buy, sell  # noqa: E402
from memecoin_radar.backtest import is_pair_flip as _is_pair_flip  # noqa: E402

TRADE_USD = 100.0

# Minimum liquidity at ENTRY for a token to count as tradeable. Below this the
# round trip costs more than most of these tokens ever move; see fomo_radar.fill.
LIQUIDITY_FLOOR = 15_000.0


@dataclass(frozen=True)
class Policy:
    name: str
    take_profit: float | None = None      # exit at entry * (1 + tp)
    stop: float | None = None             # exit at entry * (1 - stop)
    trail: float | None = None            # exit this far off the running peak
    scale_out: tuple[float, float] | None = None  # (at_gain, fraction_sold)

    def describe(self) -> str:
        return self.name


POLICIES = [
    # Jiv's 2026-09-18 proposal, asked while down to $65 from $500: "hold or
    # sell after 10% something growth". A small TP is the one shape the
    # original sweep never covered (it started at +30%), and it is exactly
    # where the round-trip cost eats the whole target, so it gets tested
    # rather than argued about.
    Policy("jiv: +10% TP, no stop", take_profit=0.10),
    Policy("+10% TP, -50% stop", take_profit=0.10, stop=0.50),
    Policy("+20% TP, -50% stop", take_profit=0.20, stop=0.50),
    Policy("jiv: +50% TP, no stop", take_profit=0.50),
    Policy("+50% TP, -50% stop", take_profit=0.50, stop=0.50),
    Policy("+30% TP, -30% stop", take_profit=0.30, stop=0.30),
    Policy("+100% TP, -50% stop", take_profit=1.00, stop=0.50),
    Policy("+200% TP, -50% stop", take_profit=2.00, stop=0.50),
    Policy("+500% TP, -50% stop", take_profit=5.00, stop=0.50),
    Policy("no TP, -50% stop (let it run)", stop=0.50),
    Policy("trail 30% off peak", trail=0.30),
    Policy("trail 50% off peak", trail=0.50),
    Policy("hold to end of tracking", None),
    # The compromise: take half off at +50% so the trade is de-risked, let the
    # rest run. Tests whether capping is the problem or sizing the cap is.
    Policy("sell 50% at +50%, trail rest 50%", scale_out=(0.50, 0.50), trail=0.50),
]


def is_pair_flip(series: list[dict], factor: float = 3.0) -> bool:
    """True when the series mixes readings from DIFFERENT pairs.

    Thin adapter over the canonical detector, which lives next to `label_one`
    in `memecoin_radar.backtest` so the runtime labeller and this study screen
    corrupt series with ONE implementation. This series uses `px`/`liq` keys.
    """
    return _is_pair_flip(series, factor=factor, price_key="px", liq_key="liq")


def load_series(db: Path) -> dict[str, list[dict]]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT mint, age_seconds, market_cap_usd, liquidity_usd
           FROM market_snapshots
           WHERE market_cap_usd > 0 AND liquidity_usd > 0
           ORDER BY mint, age_seconds"""
    ).fetchall()
    conn.close()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["mint"], []).append(
            {
                "age": float(r["age_seconds"]),
                "px": float(r["market_cap_usd"]),   # price proxy; see docstring
                "liq": float(r["liquidity_usd"]),
            }
        )
    return out


def run_one(series: list[dict], policy: Policy, cost: CostModel) -> float | None:
    """Net USD P&L of one trade. None when the series cannot support a trade."""
    entry_i = next((i for i, s in enumerate(series) if s["liq"] >= LIQUIDITY_FLOOR), None)
    if entry_i is None or entry_i >= len(series) - 1:
        return None

    entry = series[entry_i]
    opened = buy(liquidity_usd=entry["liq"], price_usd=entry["px"], cost=cost)
    held = opened.tokens
    spent = opened.usd_in + opened.fixed_cost_usd
    received = 0.0

    peak = entry["px"]
    scaled = False

    for s in series[entry_i + 1:]:
        px, liq = s["px"], s["liq"]
        peak = max(peak, px)
        gain = px / entry["px"] - 1.0

        # Partial scale-out happens first and does not close the position.
        if policy.scale_out and not scaled and gain >= policy.scale_out[0]:
            part = held * policy.scale_out[1]
            f = sell(tokens=part, liquidity_usd=liq, price_usd=px, cost=cost)
            received += f.usd_in - f.fixed_cost_usd
            held -= part
            scaled = True

        hit = (
            (policy.stop is not None and gain <= -policy.stop)
            or (policy.take_profit is not None and gain >= policy.take_profit)
            or (policy.trail is not None and px <= peak * (1.0 - policy.trail))
        )
        if hit:
            f = sell(tokens=held, liquidity_usd=liq, price_usd=px, cost=cost)
            return received + f.usd_in - f.fixed_cost_usd - spent

    last = series[-1]
    f = sell(tokens=held, liquidity_usd=last["liq"], price_usd=last["px"], cost=cost)
    return received + f.usd_in - f.fixed_cost_usd - spent


def main() -> None:
    db = Path(sys.argv[1] if len(sys.argv) > 1 else "study.sqlite3")
    # Position size is the operator's only real lever (impact is linear in it),
    # and at small sizes the FIXED per-tx cost dominates instead. Overridable
    # so an account of $65 can be modelled as itself, not as $100.
    trade_usd = float(sys.argv[2]) if len(sys.argv) > 2 else TRADE_USD
    cost = CostModel(trade_usd=trade_usd, sol_price_usd=100.0)
    all_series = load_series(db)

    candidates = {
        m: s for m, s in all_series.items()
        if len(s) >= 2 and any(x["liq"] >= LIQUIDITY_FLOOR for x in s)
    }
    tradeable = {m: s for m, s in candidates.items() if not is_pair_flip(s)}
    dropped = len(candidates) - len(tradeable)

    print(f"launches tracked      : {len(all_series):,}")
    print(f"ever tradeable (>=${LIQUIDITY_FLOOR:,.0f} liq): {len(candidates):,} "
          f"({len(candidates)/max(1,len(all_series))*100:.1f}%)")
    print(f"dropped, corrupt series (pair flip)  : {dropped} "
          f"({dropped/max(1,len(candidates))*100:.0f}% of tradeable)")
    print(f"usable                : {len(tradeable):,}")
    print(f"position size         : ${trade_usd:,.0f}   round trip is charged on both legs\n")

    print(f"{'policy':<34}{'n':>5}{'total P&L':>12}{'mean':>9}{'median':>9}{'win%':>7}{'best':>10}")
    print("-" * 86)

    results = {}
    for p in POLICIES:
        pnls = [v for v in (run_one(s, p, cost) for s in tradeable.values()) if v is not None]
        if not pnls:
            continue
        results[p.name] = pnls
        print(f"{p.describe():<34}{len(pnls):>5}{sum(pnls):>12,.0f}"
              f"{statistics.fmean(pnls):>9.2f}{statistics.median(pnls):>9.2f}"
              f"{sum(v > 0 for v in pnls)/len(pnls)*100:>6.0f}%{max(pnls):>10,.0f}")

    # Where does the money actually come from? If the top few trades are the
    # whole result, any rule that caps them is structurally wrong.
    print("\nconcentration of P&L (best policy by total):")
    best = max(results, key=lambda k: sum(results[k]))
    pnls = sorted(results[best], reverse=True)
    total = sum(pnls)
    for k in (1, 3, 5, 10):
        if len(pnls) >= k:
            print(f"  top {k:>2} trades contribute {sum(pnls[:k]):>10,.0f} "
                  f"of {total:,.0f} ({sum(pnls[:k])/total*100 if total else 0:>5.1f}%)")
    print(f"  trades that lost money   : {sum(v <= 0 for v in results[best])}/{len(results[best])}")


if __name__ == "__main__":
    main()
