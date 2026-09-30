"""What a buy actually costs on a Solana AMM, as opposed to what the chart says.

Every return figure this project has produced so far is a *price* return: peak
market cap divided by entry market cap. No position can be opened or closed at
those prices. This module is the difference between the two, and on a token
sitting at the signal's $15k liquidity floor that difference is not a rounding
error; it is most of the edge.

The dominant cost is price impact, and the thing to understand about it is that
it scales with **trade size against pool depth**, not with anything about the
token. A flat "5 bps slippage" constant of the sort a CEX backtester uses (see
`agent/backtest/engines/crypto.py`) is off by two orders of magnitude here.

The reserve arithmetic
----------------------
A constant-product pool holds a quote reserve `Q` (SOL/USDC) and a token reserve
`T`, with `Q * T = k` held invariant across a swap. DexScreener reports
`liquidity_usd`, which is the **total** value of BOTH sides. In a balanced 50/50
pool the quote side is therefore *half* of it:

    Q = liquidity_usd / 2

That halving is the single easiest thing to get wrong in this file, and getting
it wrong understates impact by exactly 2x. It has its own test.

Buying with `dx` quote (after the LP fee takes `f`):

    dx_eff = dx * (1 - f)
    dy     = T * dx_eff / (Q + dx_eff)          tokens received
    avg    = dx / dy                            price actually paid per token
    mid    = Q / T                              price the chart shows
    slip   = avg / mid - 1 = (Q + dx_eff) / (Q * (1 - f)) - 1

Concretely, a $500 buy into a $15,000 pool at a 0.25% LP fee pays **6.9%** over
mid, and pays it again on the way out. A ~14% round trip before a single
priority fee is the reason this module exists.

What is deliberately NOT modelled
---------------------------------
- **Pre-graduation pump.fun bonding curves are not 50/50 pools.** They use
  virtual reserves, and DexScreener's `liquidity_usd` for them is not two equal
  halves. `quote_share` exists so that assumption can be moved, but the honest
  statement is that this model is calibrated for graduated AMM pairs and is a
  guess on the curve.
- **The order book of other snipers.** A real fill lands behind whatever else
  was in the block. That is adverse selection, and it is modelled crudely as
  latency in `paper.py`, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# Solana charges 5,000 lamports per signature. Negligible next to a priority
# fee, included because leaving it out invites the question every time.
BASE_FEE_SOL = 0.000_005
LAMPORTS_PER_SOL = 1_000_000_000


@dataclass(frozen=True)
class CostModel:
    """Every cost between the displayed price and the realised one.

    Defaults are documented guesses, NOT measurements. `priority_fee_sol` and
    `fail_rate` in particular depend on how contested the block is, which varies
    by orders of magnitude between a quiet token and a live meta. Calibrate them
    against real fills before trusting a net number to two decimal places.
    """

    # Position size per trade, in USD. The whole point of the model: this is the
    # one input the operator controls, and impact is linear in it.
    trade_usd: float = 500.0

    # LP fee taken by the pool on each swap. Raydium CPMM is 0.25%; pump.fun's
    # curve takes 1%. The conservative default is the higher of the two.
    lp_fee: float = 0.01

    # Share of `liquidity_usd` sitting on the quote side. 0.5 for a balanced
    # constant-product pair. See the module docstring's caveat about curves.
    quote_share: float = 0.5

    # Priority fee + Jito tip per transaction. A snipe that does not tip does
    # not land, so this is not optional in practice.
    priority_fee_sol: float = 0.002
    jito_tip_sol: float = 0.0

    # Needed only to express the SOL-denominated fees in USD alongside the rest.
    sol_price_usd: float = 200.0

    # Share of swap transactions that fail outright. A failed swap still burns
    # its fee and returns no position, so the operator retries. Modelled as a
    # deterministic haircut (expected fees per SUCCESSFUL fill grow by
    # 1/(1-fail_rate)) rather than a coin flip, because a backtest that changes
    # its answer between runs cannot be used to make a decision.
    fail_rate: float = 0.10

    @property
    def fixed_cost_usd(self) -> float:
        """Expected fee burn per successful transaction, in USD."""
        per_tx_sol = BASE_FEE_SOL + self.priority_fee_sol + self.jito_tip_sol
        return per_tx_sol * self.sol_price_usd / max(1e-9, 1.0 - self.fail_rate)


@dataclass(frozen=True)
class Fill:
    """One executed side of a round trip."""

    usd_in: float
    """USD committed to the swap, before fees. Sells report proceeds gross of impact."""

    tokens: float
    """Token quantity received (buy) or sold (sell)."""

    avg_price_usd: float
    """Price actually realised per token."""

    mid_price_usd: float
    """Price the chart showed at that moment."""

    slippage_pct: float
    """Realised price vs mid, signed so that positive is always *worse* for us."""

    lp_fee_usd: float
    fixed_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        return self.lp_fee_usd + self.fixed_cost_usd + abs(self.usd_in) * self.slippage_pct


def _reserves(liquidity_usd: float, price_usd: float, quote_share: float) -> tuple[float, float]:
    """Recover (quote, token) reserves from what DexScreener actually gives us.

    Raises on unusable inputs rather than returning zeros: a pool with no
    liquidity or no price is a gap in the data, and silently treating it as a
    free fill is the failure this whole module exists to prevent.
    """
    if liquidity_usd <= 0:
        raise ValueError("liquidity_usd must be positive to model a fill")
    if price_usd <= 0:
        raise ValueError("price_usd must be positive to model a fill")
    quote = liquidity_usd * quote_share
    tokens = quote / price_usd
    return quote, tokens


def buy(*, liquidity_usd: float, price_usd: float, cost: CostModel, usd: float | None = None) -> Fill:
    """Simulate buying `usd` of a token into a pool of depth `liquidity_usd`.

    The returned `avg_price_usd` is what the position is actually opened at, and
    is always worse than `price_usd`.
    """
    spend = cost.trade_usd if usd is None else usd
    if spend <= 0:
        raise ValueError("buy size must be positive")
    quote, tokens_reserve = _reserves(liquidity_usd, price_usd, cost.quote_share)

    spend_eff = spend * (1.0 - cost.lp_fee)
    tokens_out = tokens_reserve * spend_eff / (quote + spend_eff)
    avg = spend / tokens_out
    slippage = avg / price_usd - 1.0

    return Fill(
        usd_in=spend,
        tokens=tokens_out,
        avg_price_usd=avg,
        mid_price_usd=price_usd,
        slippage_pct=slippage,
        lp_fee_usd=spend * cost.lp_fee,
        fixed_cost_usd=cost.fixed_cost_usd,
    )


def sell(*, tokens: float, liquidity_usd: float, price_usd: float, cost: CostModel) -> Fill:
    """Simulate selling `tokens` back into a pool of depth `liquidity_usd`.

    Note this reads the pool state at EXIT time, not entry. A token that ran 10x
    usually deepened its pool, which makes the exit cheaper than the entry; one
    that is being rugged has a pool collapsing toward zero, which makes the exit
    ruinous. Both are the point.
    """
    if tokens <= 0:
        raise ValueError("sell size must be positive")
    quote, tokens_reserve = _reserves(liquidity_usd, price_usd, cost.quote_share)

    tokens_eff = tokens * (1.0 - cost.lp_fee)
    usd_out = quote * tokens_eff / (tokens_reserve + tokens_eff)
    avg = usd_out / tokens
    # Signed so positive is worse for us on both sides of the trade.
    slippage = 1.0 - avg / price_usd

    return Fill(
        usd_in=usd_out,
        tokens=tokens,
        avg_price_usd=avg,
        mid_price_usd=price_usd,
        slippage_pct=slippage,
        lp_fee_usd=usd_out * cost.lp_fee / max(1e-9, 1.0 - cost.lp_fee),
        fixed_cost_usd=cost.fixed_cost_usd,
    )


def round_trip_cost_pct(*, liquidity_usd: float, cost: CostModel) -> float:
    """Total round-trip drag, as a fraction, assuming the pool does not move.

    This is the number to quote when someone asks "can we automate buying this".
    It is the hurdle the signal has to clear before it has produced a cent, and
    at the signal's own liquidity floor it is large.
    """
    price = 1.0  # Scale-free: impact depends on size vs depth, not on price.
    opened = buy(liquidity_usd=liquidity_usd, price_usd=price, cost=cost)
    closed = sell(tokens=opened.tokens, liquidity_usd=liquidity_usd, price_usd=price, cost=cost)
    return 1.0 - (closed.usd_in - closed.fixed_cost_usd) / (opened.usd_in + opened.fixed_cost_usd)


def max_size_for_impact(*, liquidity_usd: float, max_impact_pct: float, cost: CostModel) -> float:
    """Largest buy whose price impact stays under `max_impact_pct`.

    Inverts the buy equation. Used to answer the sizing question the other way
    round: given a pool this thin, how much can the bot put to work at all?

        slip = (Q + dx(1-f)) / (Q(1-f)) - 1
        dx   = Q * ((1 + slip)(1 - f) - 1) / (1 - f)
    """
    if max_impact_pct <= 0:
        raise ValueError("max_impact_pct must be positive")
    quote = liquidity_usd * cost.quote_share
    f = cost.lp_fee
    numerator = (1.0 + max_impact_pct) * (1.0 - f) - 1.0
    if numerator <= 0:
        # The LP fee alone already exceeds the impact budget.
        return 0.0
    return quote * numerator / (1.0 - f)


def with_size(cost: CostModel, trade_usd: float) -> CostModel:
    """A copy of `cost` at a different position size, for sizing sweeps."""
    return replace(cost, trade_usd=trade_usd)
