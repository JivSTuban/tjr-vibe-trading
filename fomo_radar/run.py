"""The fomo harvester loop.

    uv run python -m fomo_radar.run --dry-run --duration 300     # never posts
    uv run python -m fomo_radar.run                              # live

What it does each cycle
-----------------------
1. Poll the global feed (`/feed/tradingActivity`, 25 items, no pagination) and
   persist every item — theses AND plain swaps. The swaps are the base rate; a
   thesis hit-rate with nothing to beat is not a result.
2. For any token that just received a NEW thesis, backfill that token's real
   thesis history once, so its rank is measured against what actually happened
   rather than against the moment we started watching.
3. Score and, if it clears the gates, alert exactly once per token.
4. Every few hours, snapshot all four leaderboard windows. This also populates
   the radar's `wallets` table with Solana addresses — the free smart-money
   source PRD Phase 2 was blocked on.

The loop is deliberately conservative about alerting: most tokens never qualify,
and a quiet channel is the expected steady state, not a malfunction.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal as os_signal
import time
from datetime import datetime, timedelta, timezone

from .api import FomoAPI
from .config import FomoConfig, load_config
from .discord_sink import FomoDiscordSink
from .session import AuthError, FomoSession, RateLimited
from .signal import evaluate
from .store import FomoStore

log = logging.getLogger("fomo_radar.run")

# Verified live: only these three exist on /v2/leaderboard/{window}. The UI's
# "ALL" tab is served by something else — `all`, `alltime`, `all-time`,
# `lifetime`, `allTime` and `total` every one 404. Listing a fourth here would
# log a failure on every cycle and teach us to ignore the warning.
LEADERBOARD_WINDOWS = ("24h", "7d", "30d")

# How far back to backfill a token's thesis history the first time we see it.
# fomo's per-token endpoint honours a 500-item limit over an arbitrary window;
# 14 days covers any meme-coin lifespan with room to spare.
BACKFILL_DAYS = 14


class FomoRadar:
    def __init__(self, cfg: FomoConfig) -> None:
        self.cfg = cfg
        self.store = FomoStore(cfg.db_path)
        self._backfilled: set[tuple[str, int]] = set()
        self._lb_handles: set[str] = set()
        self._last_leaderboard = 0.0
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self, duration: float | None = None) -> None:
        deadline = time.monotonic() + duration if duration else None
        async with FomoSession(self.cfg) as session:
            api = FomoAPI(session)
            async with FomoDiscordSink(
                self.cfg.discord_webhook_url,
                max_per_min=self.cfg.max_alerts_per_min,
                max_per_hour=self.cfg.max_alerts_per_hour,
                dry_run=self.cfg.dry_run,
            ) as sink:
                self._lb_handles = self.store.leaderboard_handles()
                backoff = 0.0
                while not self._stop.is_set():
                    try:
                        await self._cycle(api, sink)
                        backoff = 0.0
                    except AuthError:
                        raise  # dead credentials must stop the daemon loudly
                    except RateLimited as exc:
                        # Exponential backoff, capped. Polling into a Cloudflare
                        # block just extends it, and every missed window is data
                        # we can never recover.
                        backoff = min(max(backoff * 2, 60.0), 900.0)
                        log.warning("%s — backing off %.0fs", exc, backoff)
                    except Exception as exc:  # noqa: BLE001
                        # A transient API blip must not kill an always-on job,
                        # but it must be visible: a silent empty feed is the
                        # failure mode this project has been bitten by most.
                        log.warning("cycle failed: %s", exc)

                    if deadline and time.monotonic() >= deadline:
                        break
                    try:
                        await asyncio.wait_for(
                            self._stop.wait(),
                            timeout=backoff or self.cfg.poll_interval_s,
                        )
                    except asyncio.TimeoutError:
                        pass
        s = self.store.stats()
        log.info(
            "stopped — %d feed items (%d theses) across %d tokens, %d alerts, "
            "%d leaderboard wallets",
            s["feed_items"], s["theses"], s["tokens"], s["alerts"],
            s["leaderboard_wallets"],
        )

    async def _cycle(self, api: FomoAPI, sink: FomoDiscordSink) -> None:
        if time.monotonic() - self._last_leaderboard > self.cfg.leaderboard_interval_s:
            await self._snapshot_leaderboard(api)

        items = await api.trading_activity(threshold=self.cfg.signal.min_thesis_usd)
        if not items:
            # Zero rows from a live feed is a source failure, never a quiet
            # market. Standing rule in this repo.
            log.warning("trading activity returned 0 items — treating as source failure")
            return

        fresh = self.store.record_items(items)
        new_theses = [i for i in fresh if i.is_thesis]
        if not new_theses:
            return
        log.info("%d new feed items (%d theses)", len(fresh), len(new_theses))

        seen: set[tuple[str, int]] = set()
        for it in new_theses:
            key = (it.token_address, it.network_id)
            if key in seen:
                continue
            seen.add(key)
            await self._consider(api, sink, it)

    async def _consider(self, api: FomoAPI, sink: FomoDiscordSink, item) -> None:
        key = (item.token_address, item.network_id)
        if self.store.already_alerted(*key):
            return

        if key not in self._backfilled:
            await self._backfill(api, item.token_address, item.network_id)
            self._backfilled.add(key)

        stats = self.store.refresh_token_stats(
            item.token_address, item.network_id, self._lb_handles
        )
        if not stats:
            return

        # Rank is recomputed post-backfill: the rank stamped at write time was
        # relative to what we had seen, which is optimistic for a token we
        # joined mid-life.
        row = self.store.conn.execute(
            """SELECT COUNT(*) AS n FROM fomo_feed_items
               WHERE token_address=? AND network_id=? AND item_type='thesis'
                 AND created_at < ?""",
            (item.token_address, item.network_id, item.created_at),
        ).fetchone()
        true_rank = int(row["n"])

        sig = evaluate(
            token_address=item.token_address,
            network_id=item.network_id,
            ticker=item.ticker,
            stats=stats,
            thesis_rank=true_rank,
            has_x_link=any("x.com" in l or "twitter.com" in l for l in item.links),
            cfg=self.cfg.signal,
        )
        if sig.tier is None:
            return

        delivered = await sink.send(sig)
        self.store.record_alert(
            token_address=sig.token_address,
            network_id=sig.network_id,
            ticker=sig.ticker,
            tier=sig.tier,
            score=sig.score,
            thesis_rank=sig.thesis_rank,
            distinct_authors=sig.distinct_authors,
            leaderboard_authors=sig.leaderboard_authors,
            total_usd=sig.total_usd,
            reason="; ".join(sig.reasons),
            delivered=delivered,
        )
        self.store.mark_alerted(sig.token_address, sig.network_id)
        log.info(
            "ALERT %s $%s score=%.0f rank=%d authors=%d lb=%d delivered=%s",
            sig.tier, sig.ticker, sig.score, sig.thesis_rank,
            sig.distinct_authors, sig.leaderboard_authors, delivered,
        )

    async def _backfill(self, api: FomoAPI, token_address: str, network_id: int) -> None:
        now = datetime.now(timezone.utc)
        after = int((now - timedelta(days=BACKFILL_DAYS)).timestamp() * 1000)
        before = int(now.timestamp() * 1000)
        try:
            history = await api.token_thesis_history(
                token_address, network_id, after_ms=after, before_ms=before,
                limit=500, threshold=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("backfill failed for %s: %s", token_address[:10], exc)
            return
        if history:
            self.store.record_items(history)
            log.debug("backfilled %d theses for %s", len(history), token_address[:10])

    async def _snapshot_leaderboard(self, api: FomoAPI) -> None:
        for window in LEADERBOARD_WINDOWS:
            try:
                traders = await api.leaderboard(window)
            except Exception as exc:  # noqa: BLE001
                log.warning("leaderboard %s failed: %s", window, exc)
                continue
            if not traders:
                log.warning("leaderboard %s returned 0 traders — source failure", window)
                continue
            self.store.record_leaderboard(window, traders)
            log.info("leaderboard %s: %d traders", window, len(traders))
        self._lb_handles = self.store.leaderboard_handles()
        self._last_leaderboard = time.monotonic()


def main() -> None:
    ap = argparse.ArgumentParser(description="fomo social-signal harvester")
    ap.add_argument("--dry-run", action="store_true", help="never post to Discord")
    ap.add_argument("--duration", type=float, default=None, help="seconds, then exit")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_config(dry_run=args.dry_run)
    radar = FomoRadar(cfg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig_name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(
                getattr(os_signal, sig_name), radar.request_stop
            )
        except (NotImplementedError, AttributeError):
            pass
    try:
        loop.run_until_complete(radar.run(duration=args.duration))
    finally:
        radar.store.close()
        loop.close()


if __name__ == "__main__":
    main()
