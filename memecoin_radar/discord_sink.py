"""Discord webhook publisher.

Delivery is the hard constraint of this whole system. Discord allows roughly
5 requests per 5 seconds per channel and ~30 per minute per webhook, while the
launch stream runs at ~24 tokens per minute. The channel physically cannot carry
the firehose, so this module enforces its own ceiling well under Discord's and
drops the quietest alerts first when saturated, rather than letting a burst of
WATCH notices crowd out an ULTRA.

Every embed carries the PRD section 10 guardrails: contract address shown in
full, age, market cap, liquidity, the rug score alongside the moon score, and
the reason the alert fired. Nothing is ever phrased as a guarantee.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .alerts import SEND_PRIORITY
from .models import Alert, Candidate

log = logging.getLogger(__name__)

# Discord's own limits, quoted here because the throttle below is derived
# from them: 5 req/5s per channel, ~30 req/min per webhook, 10 embeds and
# 6000 characters per message.
DISCORD_CHANNEL_MIN_INTERVAL_S = 1.2

COLORS: dict[str, int] = {
    "ULTRA": 0xFF3B30,
    "HOT": 0xFF9500,
    "TREND_ECHO": 0x5856D6,
    "SMART_MONEY": 0x34C759,
    "WATCH": 0x8E8E93,
    "RUG_WARNING": 0x8B0000,
}

TITLES: dict[str, str] = {
    "ULTRA": "ULTRA EARLY SIGNAL",
    "HOT": "HOT",
    "TREND_ECHO": "TREND ECHO, new coin detected",
    "SMART_MONEY": "SMART MONEY",
    "WATCH": "WATCH",
    "RUG_WARNING": "RUG WARNING",
}

DISCLAIMER = (
    "Extreme-risk microcap. Similarity to a trend does not imply legitimacy. "
    "Notifier only, no position is implied."
)


def _fmt_usd(value: float) -> str:
    if value <= 0:
        return "unknown"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def _fmt_age(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f}m"


def build_embed(alert: Alert, cand: Candidate) -> dict[str, Any]:
    """Render one alert as a Discord embed.

    Scores are reported with their coverage so a thinly-evidenced 80 cannot be
    mistaken for a fully-evidenced 80.
    """
    latest = cand.snapshots[-1] if cand.snapshots else None
    mcap = latest.market_cap_usd if latest else 0.0
    liq = latest.liquidity_usd if latest else 0.0
    vol = latest.volume_usd if latest else 0.0
    buys = latest.buys if latest else cand.buy_count
    sells = latest.sells if latest else cand.sell_count

    moon_cov = f"{cand.moon.coverage * 100:.0f}%" if cand.moon else "n/a"
    rug_cov = f"{cand.rug.coverage * 100:.0f}%" if cand.rug else "n/a"

    fields: list[dict[str, Any]] = [
        {
            "name": "Moon",
            "value": f"**{alert.moon_score:.0f}**/100\n({moon_cov} evidence)",
            "inline": True,
        },
        {
            "name": "Rug",
            "value": f"**{alert.rug_score:.0f}**/100\n({rug_cov} evidence)",
            "inline": True,
        },
        {
            "name": "Age",
            "value": _fmt_age(cand.age_seconds),
            "inline": True,
        },
        {
            "name": "Market cap",
            "value": _fmt_usd(mcap),
            "inline": True,
        },
        {
            "name": "Liquidity",
            "value": _fmt_usd(liq),
            "inline": True,
        },
        {
            "name": "Volume / flow",
            "value": f"{_fmt_usd(vol)}\n{buys} buys / {sells} sells",
            "inline": True,
        },
    ]

    if alert.relation_score > 0 and cand.related_trend is not None:
        ref = cand.related_trend
        fields.append(
            {
                "name": "Trend connection",
                "value": (
                    f"**{alert.relation_score:.0f}**/100 vs ${ref.symbol} "
                    f"({ref.momentum_state})"
                ),
                "inline": False,
            }
        )

    if alert.reasons:
        # Deduplicated and capped: a wall of reasons is unreadable on mobile and
        # risks the 6000-character embed budget.
        seen: list[str] = []
        for reason in alert.reasons:
            if reason and reason not in seen:
                seen.append(reason)
        fields.append(
            {
                "name": "Why this fired",
                "value": "\n".join(f"- {r}" for r in seen[:6])[:1000],
                "inline": False,
            }
        )

    fields.append(
        {
            "name": "Contract",
            "value": f"`{cand.mint}`\n[pump.fun](https://pump.fun/{cand.mint}) · "
                     f"[DexScreener](https://dexscreener.com/solana/{cand.mint})",
            "inline": False,
        }
    )

    # Some launches ship an empty name and ticker. Falling back to the mint stub
    # keeps the alert identifiable instead of rendering a bare "$".
    stub = cand.mint[:6]
    symbol = cand.launch.symbol.strip() or stub
    name = cand.launch.name.strip() or f"unnamed ({stub})"
    return {
        "title": f"{TITLES.get(alert.alert_type, alert.alert_type)} · ${symbol}",
        "description": f"**{name}**",
        "color": COLORS.get(alert.alert_type, 0x8E8E93),
        "fields": fields,
        "footer": {"text": DISCLAIMER},
        "timestamp": alert.ts.isoformat(),
    }


class DiscordSink:
    """Rate-limited webhook publisher with priority-aware shedding."""

    def __init__(
        self,
        webhook_url: str,
        *,
        max_per_min: int = 8,
        max_per_hour: int = 60,
        dry_run: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.max_per_min = max_per_min
        self.max_per_hour = max_per_hour
        self.dry_run = dry_run or not webhook_url
        self._client = client
        self._owns_client = client is None
        self._sent_times: list[float] = []
        self._last_send = 0.0
        self._lock = asyncio.Lock()
        self.sent = 0
        self.shed = 0

    async def __aenter__(self) -> DiscordSink:
        if self._client is None and not self.dry_run:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _budget_left(self) -> tuple[int, int]:
        now = time.monotonic()
        self._sent_times = [t for t in self._sent_times if now - t < 3600]
        last_min = sum(1 for t in self._sent_times if now - t < 60)
        return self.max_per_min - last_min, self.max_per_hour - len(self._sent_times)

    def _may_send(self, alert: Alert) -> bool:
        """Budget check that protects loud alerts from quiet ones.

        When the minute budget is nearly spent, only high-priority alerts get
        the remaining slots, so a run of WATCH notices cannot starve an ULTRA
        that arrives two seconds later.
        """
        per_min_left, per_hour_left = self._budget_left()
        if per_hour_left <= 0 or per_min_left <= 0:
            return False
        priority = SEND_PRIORITY.get(alert.alert_type, 9)
        if per_min_left <= 2 and priority >= 3:
            return False
        return True

    async def send(self, alert: Alert, cand: Candidate) -> bool:
        """Deliver one alert. Returns True when Discord accepted it."""
        async with self._lock:
            if not self._may_send(alert):
                self.shed += 1
                log.info("shed %s for %s (rate budget)", alert.alert_type, cand.mint[:8])
                return False

            # Space requests so the per-channel 5-per-5-seconds limit is never
            # approached, even during a burst.
            gap = time.monotonic() - self._last_send
            if gap < DISCORD_CHANNEL_MIN_INTERVAL_S:
                await asyncio.sleep(DISCORD_CHANNEL_MIN_INTERVAL_S - gap)

            payload = {"embeds": [build_embed(alert, cand)]}
            ok = await self._post(payload)
            self._last_send = time.monotonic()
            if ok:
                self._sent_times.append(self._last_send)
                self.sent += 1
            return ok

    async def _post(self, payload: dict[str, Any]) -> bool:
        if self.dry_run:
            embed = payload["embeds"][0]
            log.info("[dry-run] %s | %s", embed["title"], embed["description"])
            return True
        assert self._client is not None, "use DiscordSink as an async context manager"

        for attempt in range(3):
            try:
                resp = await self._client.post(self.webhook_url, json=payload)
            except httpx.HTTPError as exc:
                log.warning("discord post failed: %s", exc)
                await asyncio.sleep(1.0 + attempt)
                continue

            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 429:
                # Honour Discord's own backoff rather than guessing.
                retry_after = 1.0
                try:
                    retry_after = float(resp.json().get("retry_after", 1.0))
                except (ValueError, AttributeError, TypeError):
                    retry_after = float(resp.headers.get("Retry-After", 1.0) or 1.0)
                log.warning("discord 429, waiting %.1fs", retry_after)
                await asyncio.sleep(min(30.0, retry_after))
                continue
            if 400 <= resp.status_code < 500:
                # A malformed embed or a revoked webhook will not fix itself.
                log.error("discord rejected payload: %s %s", resp.status_code, resp.text[:200])
                return False
            await asyncio.sleep(1.0 + attempt)
        return False

    async def send_startup(self, summary: str) -> bool:
        """Post a short banner so a silent radar is distinguishable from a dead one."""
        payload = {
            "embeds": [
                {
                    "title": "Meme Coin Alpha Radar online",
                    "description": summary,
                    "color": 0x5856D6,
                    "footer": {"text": DISCLAIMER},
                }
            ]
        }
        return await self._post(payload)
