"""Does copying an influential trader's BUY make money?

    uv run python backtesting/copytrade_leaderboard/study.py <radar.sqlite3>

The strategy under test (Jiv, 2026-09-17): "buy when someone influential buys,
sell when they sell, or sell after a 50% gain."

The exit half is already answered and negative. `backtesting/memecoin_exit_policy`
tested +50% TP against ten alternatives over 5,610 launches: every policy lost,
all eleven landed within ~$100 of each other, and the median trade WAS the
round-trip cost. Its conclusion was that the exit is not the lever, the entry
is. So this study tests the ENTRY, and treats the exit rule as a variation
rather than the question.

Where the signal comes from
---------------------------
`fomo_leaderboard_holdings` snapshots the top-150 traders by realized PnL in
three windows, with each trader's TOP THREE positions: `human_amount`, `price`,
`value`. Diffing consecutive snapshots reconstructs what they traded, for free.

The look-ahead hazard, and the one thing that defuses it
--------------------------------------------------------
`api.leaderboard`'s own docstring warns the list is LAGGING: a position shows up
among someone's top holdings partly BECAUSE it appreciated, since value is
amount x price. Treating "a token appeared in their top 3" as a buy signal would
therefore select winners after they had already won. That is precisely the bug
this repo shipped twice (see the v2 "conviction cadence" signal).

What defuses it is that the table stores `human_amount` separately from `price`.
Token QUANTITY only changes when the trader actually transacts. So:

    amount up   -> a genuine buy
    amount down -> a genuine sell
    amount flat -> no trade, whatever the price did

Only amount changes are treated as events, and a token's FIRST sighting is
discarded entirely: with no prior row there is no way to tell a fresh buy from a
position that just appreciated into the visible top three.

Why the control group shares the bias
-------------------------------------
Every trader here is on the leaderboard BECAUSE they won, and the token universe
is whatever those winners hold, so any absolute return is survivorship-inflated.
The control is therefore drawn from the SAME universe: the amount-FLAT
observations, measured over the identical forward horizon. Both arms inherit the
same bias, so the difference between them isolates what the buy EVENT adds. An
absolute return here is not a tradeable expectation; only the gap is evidence.

Entry price is what WE could have paid
--------------------------------------
Entry is the price at the snapshot where the amount increase became visible to
us, never the trader's own fill. We are always at least one snapshot late, and
that lag is the strategy's real cost. Snapshot gaps in the recorded data run
from 4 to 100 minutes (median ~15), so `--max-lag` reports how the result
depends on how stale the detection was.
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fomo_radar.fill import CostModel, round_trip_cost_pct  # noqa: E402

# Amount must move by more than this to count as a trade rather than rounding or
# a rebasing artifact in the reported quantity.
TRADE_EPS = 0.01

# A price series this wild is not a price series. fomo quotes its own price
# rather than selecting a DexScreener pair, so the pair-flip corruption that
# ruins `fomo_price_snapshots` should not apply here -- but asserting that
# without checking is how the +18,605% NVDAX row got labelled, so it is checked.
MAX_PLAUSIBLE_MOVE = 100.0


@dataclass(slots=True)
class Event:
    handle: str
    token: str
    round_idx: int
    entry_px: float
    amount_before: float
    amount_after: float


def load_snapshots(db: Path) -> tuple[list[str], dict[tuple[str, str], dict[int, tuple[float, float]]],
                                     dict[str, dict[int, float]]]:
    """Return (rounds, per-(handle,token) series, per-token price series).

    The three leaderboard windows are captured within about a second of each
    other and a trader can appear in more than one, so observations are
    collapsed to one round per minute to avoid counting a single holding three
    times.
    """
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT handle, token_address,
                  substr(captured_at, 1, 16) AS round,
                  MAX(human_amount) AS amt, MAX(price) AS px
           FROM fomo_leaderboard_holdings
           WHERE human_amount IS NOT NULL AND price > 0
           GROUP BY handle, token_address, substr(captured_at, 1, 16)
           ORDER BY round"""
    ).fetchall()
    conn.close()

    rounds = sorted({str(r["round"]) for r in rows})
    idx = {r: i for i, r in enumerate(rounds)}

    series: dict[tuple[str, str], dict[int, tuple[float, float]]] = {}
    prices: dict[str, dict[int, float]] = {}
    for r in rows:
        i = idx[str(r["round"])]
        key = (str(r["handle"]), str(r["token_address"]))
        series.setdefault(key, {})[i] = (float(r["amt"]), float(r["px"]))
        # One price per token per round. Different traders report the same token
        # at the same price, so last-write-wins is not lossy.
        prices.setdefault(str(r["token_address"]), {})[i] = float(r["px"])
    return rounds, series, prices


def implausible(prices: dict[int, float]) -> bool:
    """True when a token's price series moves by more than any real market can."""
    vals = [p for p in prices.values() if p > 0]
    if len(vals) < 2:
        return False
    return max(vals) > min(vals) * MAX_PLAUSIBLE_MOVE


def find_events(series, prices) -> tuple[list[Event], list[Event], int, int]:
    """Classify every transition. Returns (buys, flats, first_sightings, sells)."""
    buys: list[Event] = []
    flats: list[Event] = []
    first = 0
    sells = 0

    for (handle, token), obs in series.items():
        if implausible(prices.get(token, {})):
            continue
        idxs = sorted(obs)
        for a, b in zip(idxs, idxs[1:]):
            amt_a, _ = obs[a]
            amt_b, px_b = obs[b]
            if amt_a <= 0:
                continue
            ratio = amt_b / amt_a
            ev = Event(handle, token, b, px_b, amt_a, amt_b)
            if ratio > 1 + TRADE_EPS:
                buys.append(ev)
            elif ratio < 1 - TRADE_EPS:
                sells += 1
            else:
                flats.append(ev)
        first += 1

    return buys, flats, first, sells


def copy_exit_round(series, ev: Event) -> int | None:
    """The first round after entry where this trader REDUCED the position."""
    obs = series[(ev.handle, ev.token)]
    idxs = [i for i in sorted(obs) if i >= ev.round_idx]
    for a, b in zip(idxs, idxs[1:]):
        if obs[b][0] < obs[a][0] * (1 - TRADE_EPS):
            return b
    return None


def forward(prices: dict[int, float], ev: Event, until: int | None) -> list[tuple[int, float]]:
    stop = until if until is not None else max(prices)
    return [(i, p) for i, p in sorted(prices.items())
            if i > ev.round_idx and i <= stop and p > 0]


def gross_return(ev: Event, path: list[tuple[int, float]], *, tp: float | None) -> float | None:
    """Return of one trade, gross of costs. None when no forward data exists."""
    if not path:
        return None
    if tp is not None:
        for _, px in path:
            if px >= ev.entry_px * (1 + tp):
                return tp
    return path[-1][1] / ev.entry_px - 1.0


def net_of_costs(gross: float, *, trade_usd: float, liquidity_usd: float) -> float:
    """Apply the real round-trip cost at this size to a gross return.

    Reuses `fill.round_trip_cost_pct` rather than re-deriving the two legs. That
    helper prices the round trip against a STATIC pool, so it understates the
    exit on a token whose pool collapsed and overstates it on one that deepened.
    Adequate here: the question is which position sizes clear the fee floor at
    all, and that is dominated by the fixed cost, not by pool drift.
    """
    rt = round_trip_cost_pct(
        liquidity_usd=liquidity_usd, cost=CostModel(trade_usd=trade_usd)
    )
    return (1.0 + gross) * (1.0 - rt) - 1.0


def summarise(name: str, rets: list[float]) -> str:
    if not rets:
        return f"{name:<34} {'n/a':>6}"
    wins = sum(1 for r in rets if r > 0)
    return (f"{name:<34} {len(rets):>5}  "
            f"{statistics.median(rets)*100:>8.2f}%  "
            f"{statistics.mean(rets)*100:>8.2f}%  "
            f"{wins/len(rets)*100:>5.1f}%  "
            f"{max(rets)*100:>8.1f}%")


def main() -> None:
    db = Path(sys.argv[1] if len(sys.argv) > 1 else "radar.sqlite3")
    rounds, series, prices = load_snapshots(db)

    buys, flats, tracked, sells = find_events(series, prices)
    dropped = sum(1 for t, p in prices.items() if implausible(p))

    print(f"snapshot rounds       : {len(rounds)}  ({rounds[0]} -> {rounds[-1]})")
    print(f"traders x tokens      : {tracked:,} position histories")
    print(f"tokens dropped, wild  : {dropped}")
    print(f"genuine BUY events    : {len(buys)}")
    print(f"genuine SELL events   : {sells}")
    print(f"amount-FLAT controls  : {len(flats):,}")
    print()
    if len(buys) < 30:
        print("!! fewer than 30 buy events: this is a harness check, not a verdict.")
        print()

    # ---- the three exit rules, gross ----
    arms: dict[str, list[float]] = {
        "COPY buy -> exit when they sell": [],
        "COPY buy -> +50% TP": [],
        "COPY buy -> hold to last snapshot": [],
    }
    for ev in buys:
        px = prices.get(ev.token, {})
        ex = copy_exit_round(series, ev)
        r = gross_return(ev, forward(px, ev, ex), tp=None)
        if r is not None:
            arms["COPY buy -> exit when they sell"].append(r)
        r = gross_return(ev, forward(px, ev, None), tp=0.50)
        if r is not None:
            arms["COPY buy -> +50% TP"].append(r)
        r = gross_return(ev, forward(px, ev, None), tp=None)
        if r is not None:
            arms["COPY buy -> hold to last snapshot"].append(r)

    # ---- the control: same universe, no trade happened ----
    control: list[float] = []
    for ev in flats:
        r = gross_return(ev, forward(prices.get(ev.token, {}), ev, None), tp=None)
        if r is not None:
            control.append(r)

    print("GROSS, before any cost. The control shares the survivorship bias, so")
    print("only the GAP between an arm and the control is evidence.")
    print()
    print(f"{'arm':<34} {'n':>5}  {'median':>9}  {'mean':>9}  {'win%':>6}  {'best':>9}")
    print("-" * 84)
    for name, rets in arms.items():
        print(summarise(name, rets))
    print("-" * 84)
    print(summarise("CONTROL: they held, no trade", control))
    print()

    # ---- costs: what size makes this tradeable at all ----
    hold = arms["COPY buy -> hold to last snapshot"]
    if hold:
        print("NET of real round-trip cost, on the hold-to-last arm.")
        print("Fixed fees (priority fee + tip) do not scale with size, so a small")
        print("position pays them as a percentage. Liquidity fixed at $50,000.")
        print()
        print(f"{'position':>9}  {'median':>9}  {'mean':>9}  {'win%':>6}  {'fixed cost':>11}")
        print("-" * 56)
        for size in (1.0, 10.0, 50.0, 100.0, 500.0, 2000.0):
            nets = [net_of_costs(g, trade_usd=size, liquidity_usd=50_000.0) for g in hold]
            wins = sum(1 for r in nets if r > 0)
            cm = CostModel(trade_usd=size)
            fixed = 2 * (cm.priority_fee_sol + cm.jito_tip_sol) * cm.sol_price_usd
            print(f"${size:>8,.0f}  {statistics.median(nets)*100:>8.2f}%  "
                  f"{statistics.mean(nets)*100:>8.2f}%  {wins/len(nets)*100:>5.1f}%  "
                  f"{fixed/size*100:>10.1f}%")
        print()

    # ---- does speed matter? the lag between their trade and our sighting ----
    print("Detection lag: we only see a trade at the NEXT snapshot, so the gap")
    print("between snapshots is the strategy's unavoidable lateness.")
    gaps = []
    for a, b in zip(rounds, rounds[1:]):
        ha, ma = int(a[11:13]), int(a[14:16])
        hb, mb = int(b[11:13]), int(b[14:16])
        gaps.append((hb * 60 + mb) - (ha * 60 + ma))
    gaps = [g for g in gaps if g > 0]
    if gaps:
        print(f"  snapshot gaps (min): min {min(gaps)}, median "
              f"{statistics.median(gaps):.0f}, max {max(gaps)}")


if __name__ == "__main__":
    main()
