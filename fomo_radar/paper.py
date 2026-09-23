"""Paper trading over recorded alerts: what a mechanical bot would actually have got.

This exists to replace the one number this project keeps quoting and cannot act
on. `memecoin_radar.backtest.label_one` reports `max_return_*`, the peak price
divided by the entry price. Nobody sells at the peak. Reading a peak return as
a strategy result is the same look-ahead mistake that produced the withdrawn v2
conviction signal, documented in `research/fomo/FINDINGS.md`: a number computed
with information from the future, describing a trade that could not be taken.

A paper trade here is fully causal. It opens at a price observed at or after the
alert, closes on a rule that only ever reads the past, and pays the AMM cost
model in `fill.py` on both sides.

Two biases you must hold while reading any output
-------------------------------------------------
The forward price series has SEVEN points (`OUTCOME_AGES_S`: 5m, 15m, 1h, 6h,
24h, 3d, 7d). Between them the price is unobserved, and that cuts both ways:

- **Stops are flattered.** A wick through the stop that recovers before the next
  snapshot is invisible, so the simulated loss is smaller than the real one.
- **Targets are penalised.** A spike through the take-profit that retraces is
  equally invisible, so a real bot watching ticks would have caught exits this
  model misses.

Every trade therefore carries `max_unobserved_gap_s`, and the aggregate reports
it. A result whose exits all land across a 5-hour blind gap is not a result.
The fix is a denser snapshot ladder, not a cleverer exit rule.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
from dataclasses import asdict, dataclass

from .config import load_config
from .fill import CostModel, buy, round_trip_cost_pct, sell, with_size
from .store import FomoStore

log = logging.getLogger("paper")

# Entry delays to sweep, in seconds. Answers the engineering question directly:
# how much does the bot lose by being slow, and is sub-minute execution worth
# building? 0 uses the alert-time mark, which only exists for alerts fired after
# the age-0 snapshot shipped.
LATENCY_LADDER_S: tuple[float, ...] = (0.0, 300.0, 900.0, 3600.0)


@dataclass(frozen=True)
class ExitPolicy:
    """A mechanical exit. Every field reads only prices at or before `now`.

    Defaults are deliberately crude. The point of the first run is not to find
    the optimal exit, it is to find out whether ANY exit survives the cost model
    on a token this thin. Tuning these before that is answered is curve-fitting
    to 14 alerts.
    """

    stop_pct: float = 0.50
    """Exit if price falls this fraction below entry."""

    take_profit_x: float | None = 3.0
    """Exit if price reaches this multiple of entry. None disables."""

    trail_pct: float | None = None
    """Exit if price falls this fraction from its peak since entry. None disables."""

    max_hold_s: float = 86_400.0
    """Exit at the first observation at or past this age, whatever the price."""


@dataclass(frozen=True)
class PaperTrade:
    token_address: str
    ticker: str
    tier: str | None

    entry_age_requested_s: float
    entry_age_actual_s: float
    entry_mid_usd: float
    entry_fill_usd: float
    entry_liquidity_usd: float

    exit_age_s: float
    exit_mid_usd: float
    exit_fill_usd: float
    exit_liquidity_usd: float
    exit_reason: str

    gross_return_pct: float
    """Mid-to-mid, what the chart shows. Shown only to be subtracted from."""

    net_return_pct: float
    """Fill-to-fill after impact, LP fees and expected fee burn. The real number."""

    net_pnl_usd: float
    buy_slippage_pct: float
    sell_slippage_pct: float
    cost_drag_pct: float
    """gross - net. How much of the move the market took."""

    observations: int
    max_unobserved_gap_s: float


def _usable(row: dict) -> bool:
    return float(row.get("price_usd") or 0) > 0 and float(row.get("liquidity_usd") or 0) > 0


def simulate(
    series: list[dict],
    *,
    policy: ExitPolicy,
    cost: CostModel,
    entry_age_s: float = 0.0,
    ticker: str = "",
    tier: str | None = None,
) -> PaperTrade | None:
    """Run one alert through the fill model and an exit rule.

    Returns None when the series cannot support a trade at all: fewer than two
    usable observations, or no observation at or after `entry_age_s`. That is a
    gap in the data and must never be reported as a flat trade.
    """
    rows = [r for r in series if _usable(r)]
    if len(rows) < 2:
        return None
    rows.sort(key=lambda r: float(r["age_seconds"]))

    entry_idx = next(
        (i for i, r in enumerate(rows) if float(r["age_seconds"]) >= entry_age_s),
        None,
    )
    # Need at least one observation AFTER entry to have anything to exit into.
    if entry_idx is None or entry_idx >= len(rows) - 1:
        return None

    entry = rows[entry_idx]
    forward = rows[entry_idx + 1:]

    entry_price = float(entry["price_usd"])
    entry_liq = float(entry["liquidity_usd"])
    opened = buy(liquidity_usd=entry_liq, price_usd=entry_price, cost=cost)

    stop_price = entry_price * (1.0 - policy.stop_pct)
    target_price = entry_price * policy.take_profit_x if policy.take_profit_x else None

    peak = entry_price
    exit_row = forward[-1]
    exit_reason = "end_of_series"

    for row in forward:
        price = float(row["price_usd"])
        age = float(row["age_seconds"])
        peak = max(peak, price)

        # Checked worst-case first: if a single snapshot step is consistent with
        # both a stop and a target, assume the stop hit. The blind gap between
        # observations makes any other ordering a claim we cannot support.
        if price <= stop_price:
            exit_row, exit_reason = row, "stop"
            break
        if target_price is not None and price >= target_price:
            exit_row, exit_reason = row, "take_profit"
            break
        if policy.trail_pct is not None and peak > 0 and price <= peak * (1.0 - policy.trail_pct):
            exit_row, exit_reason = row, "trailing"
            break
        if age >= policy.max_hold_s:
            exit_row, exit_reason = row, "time_stop"
            break

    exit_price = float(exit_row["price_usd"])
    exit_liq = float(exit_row["liquidity_usd"])
    closed = sell(tokens=opened.tokens, liquidity_usd=exit_liq, price_usd=exit_price, cost=cost)

    # Cash out the door vs cash back in. Fee burn is charged on both legs.
    spent = opened.usd_in + opened.fixed_cost_usd
    received = closed.usd_in - closed.fixed_cost_usd
    net_return = received / spent - 1.0
    gross_return = exit_price / entry_price - 1.0

    ages = [float(r["age_seconds"]) for r in rows[entry_idx:]]
    gaps = [b - a for a, b in zip(ages, ages[1:])]

    return PaperTrade(
        token_address=str(entry.get("mint") or entry.get("token_address") or ""),
        ticker=ticker,
        tier=tier,
        entry_age_requested_s=entry_age_s,
        entry_age_actual_s=float(entry["age_seconds"]),
        entry_mid_usd=entry_price,
        entry_fill_usd=opened.avg_price_usd,
        entry_liquidity_usd=entry_liq,
        exit_age_s=float(exit_row["age_seconds"]),
        exit_mid_usd=exit_price,
        exit_fill_usd=closed.avg_price_usd,
        exit_liquidity_usd=exit_liq,
        exit_reason=exit_reason,
        gross_return_pct=gross_return,
        net_return_pct=net_return,
        net_pnl_usd=received - spent,
        buy_slippage_pct=opened.slippage_pct,
        sell_slippage_pct=closed.slippage_pct,
        cost_drag_pct=gross_return - net_return,
        observations=len(ages),
        max_unobserved_gap_s=max(gaps) if gaps else 0.0,
    )


def run_all(
    store: FomoStore,
    *,
    policy: ExitPolicy,
    cost: CostModel,
    entry_age_s: float = 0.0,
) -> list[PaperTrade]:
    """Paper-trade every delivered alert. Skips alerts with no usable series."""
    trades: list[PaperTrade] = []
    for tok in store.alerted_tokens():
        addr = str(tok["token_address"])
        net = int(tok["network_id"])  # type: ignore[arg-type]
        series = store.price_series(addr, net)
        trade = simulate(
            series,
            policy=policy,
            cost=cost,
            entry_age_s=entry_age_s,
            ticker=str(tok.get("ticker") or ""),
            tier=tok.get("tier"),  # type: ignore[arg-type]
        )
        if trade is not None:
            trades.append(trade)
    return trades


def _summarise(trades: list[PaperTrade]) -> dict:
    if not trades:
        return {"trades": 0}
    nets = [t.net_return_pct for t in trades]
    gross = [t.gross_return_pct for t in trades]
    return {
        "trades": len(trades),
        "median_gross_pct": round(statistics.median(gross) * 100, 2),
        "median_net_pct": round(statistics.median(nets) * 100, 2),
        "mean_net_pct": round(statistics.fmean(nets) * 100, 2),
        "win_rate_gross": round(sum(g > 0 for g in gross) / len(gross), 3),
        "win_rate_net": round(sum(n > 0 for n in nets) / len(nets), 3),
        # The headline the whole module is for: trades that look green on the
        # chart and are red once the market is paid.
        "flipped_to_loss_by_costs": sum(
            1 for t in trades if t.gross_return_pct > 0 >= t.net_return_pct
        ),
        "total_net_pnl_usd": round(sum(t.net_pnl_usd for t in trades), 2),
        "median_cost_drag_pct": round(statistics.median(t.cost_drag_pct for t in trades) * 100, 2),
        "median_buy_slippage_pct": round(
            statistics.median(t.buy_slippage_pct for t in trades) * 100, 2
        ),
        "worst_unobserved_gap_s": max(t.max_unobserved_gap_s for t in trades),
        "exit_reasons": {
            reason: sum(1 for t in trades if t.exit_reason == reason)
            for reason in sorted({t.exit_reason for t in trades})
        },
    }


def report(
    store: FomoStore,
    *,
    policy: ExitPolicy,
    cost: CostModel,
) -> dict:
    """Full paper-trading report: overall, by tier, and by entry latency."""
    trades = run_all(store, policy=policy, cost=cost, entry_age_s=0.0)
    if not trades:
        return {
            "error": (
                "no alert has a usable forward price series yet. Either nothing has "
                "been alerted, or outcome tracking has not recorded two readings for "
                "any alerted token. This is a data gap, not a result."
            ),
            "alerts_seen": len(store.alerted_tokens()),
        }

    by_tier: dict[str, list[PaperTrade]] = {}
    for t in trades:
        by_tier.setdefault(t.tier or "UNKNOWN", []).append(t)

    latency: dict[str, dict] = {}
    for age in LATENCY_LADDER_S:
        at_age = run_all(store, policy=policy, cost=cost, entry_age_s=age)
        latency[f"{int(age)}s"] = _summarise(at_age)

    return {
        "position_size_usd": cost.trade_usd,
        "policy": asdict(policy),
        "cost_model": {
            "lp_fee": cost.lp_fee,
            "fixed_cost_usd_per_tx": round(cost.fixed_cost_usd, 4),
            "fail_rate": cost.fail_rate,
        },
        "hurdle_round_trip_pct": {
            f"${int(liq/1000)}k_pool": round(
                round_trip_cost_pct(liquidity_usd=liq, cost=cost) * 100, 2
            )
            for liq in (15_000.0, 30_000.0, 100_000.0, 500_000.0)
        },
        "overall": _summarise(trades),
        "by_tier": {tier: _summarise(ts) for tier, ts in sorted(by_tier.items())},
        "by_entry_latency": latency,
        "verdict": _verdict(trades, cost),
    }


def _verdict(trades: list[PaperTrade], cost: CostModel) -> str:
    """State plainly whether a bot would have made money, and refuse to overclaim."""
    n = len(trades)
    median_net = statistics.median(t.net_return_pct for t in trades)
    if n < 30:
        return (
            f"{n} paper trades. Far too few to conclude anything: the median net of "
            f"{median_net * 100:.1f}% is an anecdote, not an edge. Do not size a live "
            "bot off this until the count is well past 30."
        )
    if median_net <= 0:
        return (
            f"Median net {median_net * 100:.1f}% over {n} trades at ${cost.trade_usd:.0f} size. "
            "The signal does not survive its own execution costs. Automating buys on it "
            "would convert a measured ordering into a measured loss."
        )
    return (
        f"Median net {median_net * 100:.1f}% over {n} trades at ${cost.trade_usd:.0f} size, "
        "after impact and fees. Positive, but check the entry-latency table before "
        "believing a bot can capture it."
    )


def size_sweep(
    store: FomoStore,
    *,
    policy: ExitPolicy,
    cost: CostModel,
    sizes: tuple[float, ...] = (100.0, 250.0, 500.0, 1000.0, 2500.0),
) -> dict:
    """Net result at several position sizes.

    Impact is linear in size while the edge is not, so there is a size above
    which the strategy pays the pool more than it earns. This finds it.
    """
    out = {}
    for size in sizes:
        trades = run_all(store, policy=policy, cost=with_size(cost, size), entry_age_s=0.0)
        out[f"${int(size)}"] = _summarise(trades)
    return out


def _live_sol_price(fallback: float = 200.0) -> float:
    """SOL/USD from DexScreener, falling back loudly rather than silently."""
    from memecoin_radar.sources.dexscreener import DexScreenerClient

    async def _fetch() -> float:
        async with DexScreenerClient() as dex:
            return await dex.sol_price_usd()

    try:
        price = asyncio.run(_fetch())
    except Exception as exc:  # noqa: BLE001
        log.warning("SOL price lookup failed (%s); using $%.0f", exc, fallback)
        return fallback
    if price <= 0:
        log.warning("SOL price came back as %s; using $%.0f", price, fallback)
        return fallback
    log.info("SOL price $%.2f", price)
    return price


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-fill simulation over recorded fomo alerts")
    parser.add_argument("command", choices=["report", "sizes", "hurdle", "trades"])
    parser.add_argument("--size", type=float, default=500.0, help="position size in USD")
    parser.add_argument("--stop", type=float, default=0.50, help="stop loss as a fraction")
    parser.add_argument("--target", type=float, default=3.0, help="take profit multiple, 0 to disable")
    parser.add_argument("--trail", type=float, default=0.0, help="trailing stop fraction, 0 to disable")
    parser.add_argument("--hold-hours", type=float, default=24.0)
    parser.add_argument("--lp-fee", type=float, default=0.01)
    parser.add_argument(
        "--sol-price", type=float, default=0.0,
        help="SOL/USD for fee conversion. Default 0 fetches it live from DexScreener.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # Fees are denominated in SOL, so a hardcoded SOL price silently decays into
    # a wrong fee every week. Fetch it unless explicitly pinned for a repeatable run.
    sol_price = args.sol_price or _live_sol_price()
    cost = CostModel(trade_usd=args.size, lp_fee=args.lp_fee, sol_price_usd=sol_price)
    policy = ExitPolicy(
        stop_pct=args.stop,
        take_profit_x=args.target or None,
        trail_pct=args.trail or None,
        max_hold_s=args.hold_hours * 3600.0,
    )

    cfg = load_config()
    store = FomoStore(cfg.db_path)
    try:
        if args.command == "hurdle":
            print(json.dumps({
                f"${int(liq/1000)}k_pool": {
                    "round_trip_cost_pct": round(
                        round_trip_cost_pct(liquidity_usd=liq, cost=cost) * 100, 2
                    ),
                }
                for liq in (5_000.0, 15_000.0, 30_000.0, 100_000.0, 500_000.0)
            }, indent=2))
        elif args.command == "sizes":
            print(json.dumps(size_sweep(store, policy=policy, cost=cost), indent=2))
        elif args.command == "trades":
            trades = run_all(store, policy=policy, cost=cost)
            print(json.dumps([asdict(t) for t in trades], indent=2))
        else:
            print(json.dumps(report(store, policy=policy, cost=cost), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
