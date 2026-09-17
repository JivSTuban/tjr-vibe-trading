"""Discord delivery for fomo signals.

Reuses `memecoin_radar.discord_sink.DiscordSink` for the rate governor and HTTP
plumbing rather than reimplementing it (that class already encodes Discord's
5-per-5s per-channel limit and priority-aware shedding, both of which were tuned
against a real flooding incident). Only the embed is new, because the existing
`build_embed` is bound to the radar's Alert/Candidate dataclasses.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from memecoin_radar.discord_sink import DiscordSink

from .config import SOLANA_NETWORK_ID
from .signal import TIER_CONVICTION, TIER_HOT, TIER_PRIORITY, TokenSignal

log = logging.getLogger("fomo_radar.discord")

TIER_COLOR = {
    TIER_CONVICTION: 0x2ECC71,
    TIER_HOT: 0xF1C40F,
}
DEFAULT_COLOR = 0x95A5A6

NETWORK_SLUG = {SOLANA_NETWORK_ID: "solana", 1: "ethereum", 56: "bnb", 8453: "base"}


def token_url(sig: TokenSignal) -> str:
    slug = NETWORK_SLUG.get(sig.network_id, str(sig.network_id))
    return f"https://fomo.family/tokens/{slug}/{sig.token_address}"


def _trim(text: str, limit: int = 300) -> str:
    """Discord field values cap at 1024 chars; keep well inside and tidy."""
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def build_embed(sig: TokenSignal) -> dict[str, Any]:
    """The alert. Names the actual traders and quotes the live thesis.

    The point of the embed is that the claim is checkable: which handle, how
    many theses, how early they committed, how much is on the line, and what
    they last said. A score with no author behind it is not auditable.
    """
    ticker = sig.ticker or sig.token_address[:8]
    c = sig.cluster
    top = c.top

    fields: list[dict[str, Any]] = []

    if top is not None:
        lb = " · top-150" if top.is_leaderboard else ""
        fields.append(
            {
                "name": "Lead conviction",
                "value": (
                    f"**@{top.handle}**{lb}\n"
                    f"{top.theses} theses over {top.span_hours:.0f}h · "
                    f"first at #{top.first_rank + 1} of "
                    f"{top.total_theses_on_token} ({top.first_pct * 100:.0f}% in)\n"
                    f"${top.position_usd:,.0f} held at {top.pnl_pct:+.0f}%"
                ),
                "inline": False,
            }
        )

    others = [a for a in c.authors[1:4]]
    if others:
        fields.append(
            {
                "name": f"Also holding ({c.count} conviction authors total)",
                "value": "\n".join(
                    f"@{a.handle}{' · top-150' if a.is_leaderboard else ''} — "
                    f"{a.theses} theses · ${a.position_usd:,.0f} at {a.pnl_pct:+.0f}%"
                    for a in others
                ),
                "inline": False,
            }
        )

    liq = sig.liquidity
    fields.append(
        {
            "name": "Market",
            "value": (
                f"liq ${liq.liquidity_usd:,.0f} · 1h vol ${liq.volume_h1_usd:,.0f}\n"
                f"mc ${liq.market_cap_usd:,.0f} · "
                f"{liq.buys_m5}B/{liq.sells_m5}S in 5m"
            ),
            "inline": True,
        }
    )
    fields.append(
        {
            "name": "Cluster",
            "value": (
                f"${c.capital_usd:,.0f} conviction capital\n"
                f"{c.leaderboard_count} top-150 · {c.considered} authors seen"
            ),
            "inline": True,
        }
    )

    if top is not None and top.last_text:
        fields.append(
            {
                "name": f"@{top.handle}'s latest thesis",
                "value": _trim(top.last_text),
                "inline": False,
            }
        )

    return {
        "title": f"{sig.tier} · ${ticker}",
        "url": token_url(sig),
        "color": TIER_COLOR.get(sig.tier or "", DEFAULT_COLOR),
        "description": " · ".join(sig.reasons) if sig.reasons else "—",
        "fields": fields,
        "footer": {
            "text": (
                f"fomo conviction · score {sig.score:.0f} · "
                f"{sig.token_address[:10]}… · not validated, no hit rate yet"
            )
        },
    }


class FomoDiscordSink:
    """Thin wrapper that reuses DiscordSink's governor with a fomo embed."""

    def __init__(
        self,
        webhook_url: str,
        *,
        max_per_min: int = 4,
        max_per_hour: int = 20,
        dry_run: bool = False,
    ) -> None:
        self._sink = DiscordSink(
            webhook_url,
            max_per_min=max_per_min,
            max_per_hour=max_per_hour,
            dry_run=dry_run,
        )
        self.sent = 0
        self.shed = 0

    async def __aenter__(self) -> FomoDiscordSink:
        await self._sink.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._sink.__aexit__(*exc)

    async def send(self, sig: TokenSignal) -> bool:
        per_min_left, per_hour_left = self._sink._budget_left()
        if per_hour_left <= 0 or per_min_left <= 0:
            self.shed += 1
            log.info("shed %s for %s (rate budget)", sig.tier, sig.ticker)
            return False
        # Protect the loud tiers when the minute budget is nearly spent, the
        # same rule the radar's own sink applies.
        if per_min_left <= 1 and TIER_PRIORITY.get(sig.tier or "", 9) >= 3:
            self.shed += 1
            return False

        # `_post` already short-circuits and logs in dry-run mode, so there is
        # no separate branch here.
        ok = await self._sink._post({"embeds": [build_embed(sig)]})
        if ok:
            self._sink._sent_times.append(time.monotonic())
            self._sink._last_send = time.monotonic()
            self.sent += 1
        return ok
