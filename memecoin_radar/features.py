"""Acceleration features: the PRD's section 2.3 "score acceleration, not size".

Everything here is a rate of change computed from the snapshot series the
enricher records, so a token with a big but flat volume looks different from one
with a small and doubling volume.

One honesty note that shapes several features: DexScreener exposes transaction
COUNTS (`txns.m5.buys`), not unique buyers. On the free path the radar therefore
measures buy-transaction acceleration and reports unique-buyer acceleration as
unavailable, rather than passing off tx counts as distinct wallets. Real unique
buyers require either the metered PumpPortal trade stream or per-signature RPC
parsing.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import MarketSnapshot


@dataclass(slots=True)
class FlowFeatures:
    """Derived rates for one candidate at its current age."""

    volume_rate_usd_per_min: float = 0.0
    volume_accel: float = 0.0  # ratio of latest rate to prior rate
    buy_tx_rate_per_min: float = 0.0
    buy_tx_accel: float = 0.0
    buy_ratio: float = 0.5
    holder_growth_per_min: float | None = None
    unique_buyer_accel: float | None = None  # free path cannot measure this
    liquidity_usd: float = 0.0
    market_cap_usd: float = 0.0
    net_liquidity_change: float = 0.0
    samples: int = 0


def _rate(delta: float, seconds: float) -> float:
    if seconds <= 0:
        return 0.0
    return delta / seconds * 60.0


def compute_flow(snapshots: list[MarketSnapshot]) -> FlowFeatures:
    """Turn a snapshot series into rates and accelerations.

    With one snapshot only levels are known, so rates stay zero and the Moon
    scorer treats acceleration as unavailable. That is the correct answer at
    second zero, and it is why the PRD enriches at +1m/+3m/+5m instead of
    scoring once.
    """
    ordered = sorted(snapshots, key=lambda s: s.age_seconds)
    feat = FlowFeatures(samples=len(ordered))
    if not ordered:
        return feat

    latest = ordered[-1]
    feat.liquidity_usd = latest.liquidity_usd
    feat.market_cap_usd = latest.market_cap_usd
    total = latest.buys + latest.sells
    feat.buy_ratio = latest.buys / total if total else 0.5

    if len(ordered) < 2:
        return feat

    prev = ordered[-2]
    span = latest.age_seconds - prev.age_seconds
    feat.volume_rate_usd_per_min = _rate(latest.volume_usd - prev.volume_usd, span)
    feat.buy_tx_rate_per_min = _rate(float(latest.buys - prev.buys), span)
    feat.net_liquidity_change = latest.liquidity_usd - prev.liquidity_usd

    if len(ordered) >= 3:
        mid = ordered[-3]
        prior_span = prev.age_seconds - mid.age_seconds
        prior_vol_rate = _rate(prev.volume_usd - mid.volume_usd, prior_span)
        prior_buy_rate = _rate(float(prev.buys - mid.buys), prior_span)
        # Guarded ratios: a zero prior rate with a positive current rate is
        # genuine acceleration from a standing start, capped so it cannot
        # dominate the whole score.
        feat.volume_accel = _safe_ratio(feat.volume_rate_usd_per_min, prior_vol_rate)
        feat.buy_tx_accel = _safe_ratio(feat.buy_tx_rate_per_min, prior_buy_rate)
    elif feat.volume_rate_usd_per_min > 0:
        feat.volume_accel = 1.0
        feat.buy_tx_accel = 1.0

    holder_points = [s for s in ordered if s.holder_count > 0]
    if len(holder_points) >= 2:
        a, b = holder_points[-2], holder_points[-1]
        feat.holder_growth_per_min = _rate(
            float(b.holder_count - a.holder_count), b.age_seconds - a.age_seconds
        )
    return feat


def _safe_ratio(current: float, prior: float, cap: float = 10.0) -> float:
    """Ratio of two rates that stays finite when the prior rate is zero."""
    if prior > 0:
        return min(cap, current / prior)
    return min(cap, 2.0) if current > 0 else 0.0
