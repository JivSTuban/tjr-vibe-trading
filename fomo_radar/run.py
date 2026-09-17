"""The fomo harvester loop.

    uv run python -m fomo_radar.run --dry-run --duration 300     # never posts
    uv run python -m fomo_radar.run                              # live

What it does each cycle
-----------------------
1. Poll the global feed (`/feed/tradingActivity`, 25 items, no pagination) and
   persist every item — theses AND plain swaps. The swaps are the base rate; a
   thesis hit-rate with nothing to beat is not a result.
2. For any token that just received a NEW thesis, backfill that token's real
   thesis history once, so author cadence and first-thesis earliness are
   measured against what actually happened rather than against the moment we
   started watching.
3. Build the author conviction profiles, check there is a live market in the
   token, score, and alert — re-alerting only on a genuine tier upgrade.
4. Every few hours, snapshot all four leaderboard windows. This also populates
   the radar's `wallets` table with Solana addresses — the free smart-money
   source PRD Phase 2 was blocked on.

Step 3 is where v2 differs from v1. v1 required a token to be inside its first
10 theses ever, which no established token can satisfy once we join its
timeline at rank ~500 — over 17 hours it watched ALLINU take positions of
$328k/$206k/$202k at +742%/+606%/+593% and alerted nothing. v2 asks instead
whether any individual author committed EARLY and has kept posting since, which
is answerable from backfilled history at any arrival time, and it refuses to
alert on a token with no live market.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal as os_signal
import time
from datetime import datetime, timedelta, timezone

from memecoin_radar.sources.dexscreener import DexScreenerClient

from .api import FomoAPI
from .config import FomoConfig, load_config
from .conviction import build_cluster
from .discord_sink import FomoDiscordSink
from .session import AuthError, FomoSession, RateLimited
from .signal import TIER_PRIORITY, LiquidityState, evaluate
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

# How often the loop says it is alive even when nothing new arrived.
HEARTBEAT_S = 300.0

# How long a DexScreener market snapshot stays usable. One token can take
# several theses a minute during a run, and re-fetching per thesis would burn
# the rate budget for no new information.
LIQUIDITY_TTL_S = 90.0


class FomoRadar:
    def __init__(self, cfg: FomoConfig) -> None:
        self.cfg = cfg
        self.store = FomoStore(cfg.db_path)
        self._backfilled: set[tuple[str, int]] = set()
        self._liq_cache: dict[str, tuple[float, LiquidityState]] = {}
        self._lb_handles: set[str] = set()
        self._last_leaderboard = 0.0
        self._last_beat = 0.0
        self._polls = 0
        self._items_since_beat = 0
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
        self._polls += 1
        self._items_since_beat += len(fresh)

        # Heartbeat. Without it the loop logs nothing at all while the feed is
        # quiet, so a healthy idle harvester and a stalled one look identical
        # from the log — the false-green shape this project keeps hitting. The
        # feed genuinely does go quiet (25 items can span ~an hour), so silence
        # is normal and must still be distinguishable from death.
        if time.monotonic() - self._last_beat >= HEARTBEAT_S:
            log.info(
                "heartbeat: %d polls, %d new items since last beat, %d tokens tracked",
                self._polls, self._items_since_beat, self.store.stats()["tokens"],
            )
            self._last_beat = time.monotonic()
            self._polls = 0
            self._items_since_beat = 0

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

        if key not in self._backfilled:
            await self._backfill(api, item.token_address, item.network_id)
            self._backfilled.add(key)

        stats = self.store.refresh_token_stats(
            item.token_address, item.network_id, self._lb_handles
        )
        if not stats:
            return

        # Author cadence and first-thesis earliness are computed from the FULL
        # backfilled history, so they do not depend on when we started watching.
        profiles = self.store.author_profiles(
            item.token_address, item.network_id, self._lb_handles
        )
        cluster = build_cluster(
            profiles,
            min_theses=self.cfg.signal.min_author_theses,
            min_theses_leaderboard=self.cfg.signal.min_author_theses_leaderboard,
            max_first_pct=self.cfg.signal.max_first_thesis_pct,
            min_position_usd=self.cfg.signal.min_thesis_usd,
        )
        # Cheap exit before spending a DexScreener call: no conviction author
        # means no alert regardless of what the market looks like.
        if cluster.count < 1:
            return

        liquidity = await self._liquidity(item.token_address)

        sig = evaluate(
            token_address=item.token_address,
            network_id=item.network_id,
            ticker=item.ticker,
            cluster=cluster,
            liquidity=liquidity,
            total_usd=float(stats.get("total_usd") or 0.0),
            cfg=self.cfg.signal,
        )
        if sig.tier is None:
            if sig.blocked_by:
                # Logged, not silent: "a conviction cluster existed but the
                # token failed a hard gate" is the single most useful line for
                # telling a working filter apart from a broken one.
                log.info(
                    "skip $%s — %d conviction author(s) but blocked: %s",
                    item.ticker, cluster.count, "; ".join(sig.blocked_by),
                )
            return

        # Alert once per tier, and again only on a real upgrade.
        prior = self.store.best_tier_so_far(*key)
        if prior is not None:
            if not self.cfg.signal.realert_on_upgrade:
                return
            if TIER_PRIORITY[sig.tier] >= TIER_PRIORITY[prior]:
                return
            log.info("$%s upgrading %s -> %s", item.ticker, prior, sig.tier)

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

    async def _liquidity(self, token_address: str) -> LiquidityState:
        """Current market state for one token, via the sibling radar's client.

        Reuses `memecoin_radar.sources.dexscreener` rather than adding a second
        DexScreener implementation — it already carries the rate limiter, the
        30-address batching and the primary-pair selection.

        A failed or empty lookup returns `known=False`, which FAILS the
        liquidity gate. Scoring an unknown token as zero-liquidity would be a
        silent penalty; scoring it as fine would be exactly the bug being fixed.
        Cached briefly because one token can receive several theses a minute.
        """
        now = time.monotonic()
        hit = self._liq_cache.get(token_address)
        if hit and now - hit[0] < LIQUIDITY_TTL_S:
            return hit[1]
        try:
            async with DexScreenerClient() as dex:
                states = await dex.token_states([token_address])
        except Exception as exc:  # noqa: BLE001
            log.warning("liquidity lookup failed for %s: %s", token_address[:10], exc)
            return LiquidityState(known=False)
        st = states.get(token_address)
        state = (
            LiquidityState(
                known=True,
                liquidity_usd=st.liquidity_usd,
                volume_h1_usd=st.volume_h1_usd,
                market_cap_usd=st.market_cap_usd,
                buys_m5=st.buys_m5,
                sells_m5=st.sells_m5,
            )
            if st is not None
            else LiquidityState(known=False)
        )
        self._liq_cache[token_address] = (now, state)
        return state

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
