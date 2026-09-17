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


def build_embed(sig: TokenSignal) -> dict[str, Any]:
    ticker = sig.ticker or sig.token_address[:8]
    fields = [
        {
            "name": "Earliness",
            "value": f"thesis #{sig.thesis_rank + 1} · {sig.minutes_since_first:.0f}m since first",
            "inline": True,
        },
        {
            "name": "Conviction",
            "value": f"{sig.distinct_authors} authors · ${sig.total_usd:,.0f} total",
            "inline": True,
        },
        {
            "name": "Largest position",
            "value": f"${sig.max_usd:,.0f}",
            "inline": True,
        },
    ]
    if sig.leaderboard_authors:
        fields.append(
            {
                "name": "Leaderboard traders",
                "value": (
                    f"{sig.leaderboard_authors} in "
                    "(lagging quality marker, not discovery)"
                ),
                "inline": True,
            }
        )
    if sig.has_x_link:
        # Shown as context only. Measured to be a size proxy that inverts above
        # $5k, so it must not read as part of the score.
        fields.append(
            {"name": "Source", "value": "X link in thesis (not scored)", "inline": True}
        )

    return {
        "title": f"{sig.tier} · ${ticker}",
        "url": token_url(sig),
        "color": TIER_COLOR.get(sig.tier or "", DEFAULT_COLOR),
        "description": " · ".join(sig.reasons) if sig.reasons else "—",
        "fields": fields,
        "footer": {
            "text": (
                f"fomo social · score {sig.score:.0f} · "
                f"{sig.token_address[:10]}…"
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
