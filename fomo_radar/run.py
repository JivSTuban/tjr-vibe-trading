"""The fomo harvester loop.

    uv run python -m fomo_radar.run --dry-run --duration 300     # never posts
    uv run python -m fomo_radar.run                              # live

What it does each cycle
-----------------------
1. Poll the global feed (`/feed/tradingActivity`, 25 items, no pagination) and
   persist every item — theses AND plain swaps. The swaps are the base rate; a
   thesis hit-rate with nothing to beat is not a result.
2. For any token that just received a NEW thesis, backfill its real thesis
   history once so the ABSOLUTE rank of that thesis is correct rather than
   relative to when we started watching.
3. If we are early (rank under `max_thesis_rank`) and the token has a live
   market, alert. Everything else is dropped, loudly enough to audit.
4. Record forward prices for alerted tokens so outcomes can be labelled. Until
   that table has rows, NOTHING here is validated.
5. Every few hours, snapshot all four leaderboard windows. This also populates
   the radar's `wallets` table with Solana addresses.

Step 3 is v1's rule, restored. v2 replaced it with author "conviction cadence"
and produced trophies: a $CATE alert on a $67M token whose lead author was
already +1735% after 436 theses over 333 hours. Both v2 features needed
information from the future — thesis count accumulates only because the token
ran, and `first_rank/total` needs the eventual total. Stripping them made the
measurement better (first 20 theses: +164.6% median / 81.0% win, against
+68.3% / 72.4% for the v2 gate and a +10.9% / 57.1% baseline).

v1's real defect was never the gate, it was the INPUT: the global feed shows
tokens at rank 70-500 regardless of `threshold` (verified at 0/10/100/1000), so
an early-rank gate starves. `discovery.py` is the fix — it joins the sibling
radar's pump.fun launch stream against fomo thesis history, which reaches tokens
at rank 1-20 by construction.
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
from .config import SOLANA_NETWORK_ID, FomoConfig, load_config
from .conviction import build_cluster
from .discord_sink import FomoDiscordSink
from .discovery import MAX_CHECKS_PER_SWEEP, RECHECK_S, liquid_launches
from .session import AuthError, FomoSession, RateLimited
from .signal import TIER_PRIORITY, LiquidityState, evaluate
from .store import FomoStore

log = logging.getLogger("fomo_radar.run")


def _parse_iso(ts: str) -> datetime | None:
    """Tolerant ISO parse; a malformed timestamp must not kill the loop."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


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

# Ages, measured from the FIRST delivered alert, at which an alerted token's
# price is recorded so the outcome can be labelled later.
#
# This is the missing half of the project. Every gate in `signal.py` is a
# measured *ordering* on a survivorship-biased sample; none of it is a validated
# hit rate until alerts are tracked forward. The spacing is longer than the
# sibling radar's because a conviction thesis plays out over hours to days, not
# over the first five minutes of a launch. The 1h/6h/24h/7d marks line up with
# `memecoin_radar.backtest.RETURN_WINDOWS` so its labeller reads these directly.
OUTCOME_AGES_S = (
    300.0, 900.0, 3600.0, 21_600.0, 86_400.0, 259_200.0, 604_800.0,
)

# How often the loop checks whether any alerted token is due a price reading.
OUTCOME_TICK_S = 120.0

# How often to sweep the sibling radar's launch stream for socially-young
# tokens. Social footprint grows over minutes to hours, so this is deliberately
# slower than the feed poll.
DISCOVERY_TICK_S = 180.0


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
        self._last_outcome_tick = 0.0
        self._last_discovery = 0.0
        self._discovery_seen: dict[str, float] = {}
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

        if time.monotonic() - self._last_outcome_tick > OUTCOME_TICK_S:
            await self._track_outcomes()
            self._last_outcome_tick = time.monotonic()

        if time.monotonic() - self._last_discovery > DISCOVERY_TICK_S:
            await self._discover_early(api, sink)
            self._last_discovery = time.monotonic()

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

        # ABSOLUTE thesis rank: how many theses existed before this one. This is
        # the signal, and it is recomputed post-backfill because the rank stamped
        # at write time was relative to what we had seen. Not normalised by the
        # token's eventual thesis count — that is future information, and using
        # it is what made v2 alert on tokens that had already run.
        row = self.store.conn.execute(
            """SELECT COUNT(*) AS n FROM fomo_feed_items
               WHERE token_address=? AND network_id=? AND item_type='thesis'
                 AND created_at < ?""",
            (item.token_address, item.network_id, item.created_at),
        ).fetchone()
        thesis_rank = int(row["n"])

        # Cheap exit before spending a DexScreener call. Most feed items are on
        # tokens with hundreds of theses; those are reports, not signals.
        if thesis_rank >= self.cfg.signal.max_thesis_rank:
            return

        # Cluster is for DISPLAY only now — who is in and how big. Every one of
        # its features is measured after the fact, so none of them score.
        profiles = self.store.author_profiles(
            item.token_address, item.network_id, self._lb_handles
        )
        cluster = build_cluster(profiles, min_position_usd=0.0, max_first_pct=1.0,
                               min_theses=1, min_theses_leaderboard=1)

        # The feed is multi-chain and our liquidity source is not. Verified
        # 2026-09-17: tokens on network 4663 (ASTEROID, HOTDOG, JEV) return no
        # DexScreener pair even when queried individually, so they can never
        # satisfy the liquidity gate. Left implicit, they look like tokens with
        # a dead market forever; said out loud, they are a coverage gap.
        if item.network_id != SOLANA_NETWORK_ID:
            log.info(
                "skip $%s at thesis #%d — network %d is outside our price "
                "coverage (Solana only)",
                item.ticker, thesis_rank + 1, item.network_id,
            )
            return

        liquidity = await self._liquidity(item.token_address)

        sig = evaluate(
            token_address=item.token_address,
            network_id=item.network_id,
            ticker=item.ticker,
            thesis_rank=thesis_rank,
            cluster=cluster,
            liquidity=liquidity,
            largest_usd=float(stats.get("max_usd") or 0.0),
            total_usd=float(stats.get("total_usd") or 0.0),
            cfg=self.cfg.signal,
        )
        if sig.tier is None:
            if sig.blocked_by:
                # Logged, not silent: "we were early but the token failed a hard
                # gate" is the single most useful line for telling a working
                # filter apart from a broken one.
                log.info(
                    "skip $%s at thesis #%d — blocked: %s",
                    item.ticker, thesis_rank + 1, "; ".join(sig.blocked_by),
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

    async def _discover_early(self, api: FomoAPI, sink: FomoDiscordSink) -> None:
        """Find socially-young tokens via the sibling radar's launch stream.

        This is the input fix that makes an early-rank gate able to fire at all.
        The global feed cannot reach rank<=20 at any threshold, but a pump.fun
        launch that just developed a market has almost no social footprint by
        construction. See `discovery.py` for the measurement.
        """
        candidates = liquid_launches(self.store.conn)
        if not candidates:
            return

        now = time.monotonic()
        checked = 0
        early = 0
        for cand in candidates:
            last = self._discovery_seen.get(cand.mint, 0.0)
            if last and now - last < RECHECK_S:
                continue
            self._discovery_seen[cand.mint] = now
            checked += 1
            if checked > MAX_CHECKS_PER_SWEEP:
                # Budgeted per sweep: 60 calls in one burst tripped a real
                # Cloudflare 429, and a backoff stalls the feed poll as well.
                log.info(
                    "discovery: hit the %d-call sweep budget, %d candidates "
                    "deferred to the next sweep",
                    MAX_CHECKS_PER_SWEEP, len(candidates) - checked,
                )
                break

            history = await self._thesis_history(api, cand.mint, SOLANA_NETWORK_ID)
            if not history:
                continue
            # Persist regardless: these rows are the base rate, and they make
            # the rank correct for every later evaluation.
            self.store.record_items(history)
            if len(history) >= self.cfg.signal.max_thesis_rank:
                continue
            early += 1
            # Evaluate on the newest thesis, which is the one that just told us
            # the token has social traction while still being early.
            newest = max(history, key=lambda h: h.created_at)
            await self._consider(api, sink, newest)

        if checked:
            log.info(
                "discovery: checked %d liquid launches, %d were socially early "
                "(<%d theses)",
                checked, early, self.cfg.signal.max_thesis_rank,
            )

    async def _thesis_history(self, api: FomoAPI, mint: str, network_id: int):
        now = datetime.now(timezone.utc)
        after = int((now - timedelta(days=BACKFILL_DAYS)).timestamp() * 1000)
        before = int(now.timestamp() * 1000)
        try:
            return await api.token_thesis_history(
                mint, network_id, after_ms=after, before_ms=before,
                limit=500, threshold=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("thesis history failed for %s: %s", mint[:10], exc)
            return []

    async def _track_outcomes(self) -> None:
        """Record forward prices for alerted tokens that are due a reading.

        Without this the radar can never be validated: it would keep producing
        alerts that are never scored against what happened next, which is the
        state both radars have been in since they shipped (zero labelled
        outcomes). Reads are batched into one DexScreener call.
        """
        now = datetime.now(timezone.utc)
        due: list[tuple[dict, float]] = []
        for tok in self.store.alerted_tokens():
            first = _parse_iso(str(tok["first_alert"]))
            if first is None:
                continue
            age = (now - first).total_seconds()
            recorded = self.store.recorded_ages(
                str(tok["token_address"]), int(tok["network_id"])  # type: ignore[arg-type]
            )
            # The oldest unrecorded mark this token has already passed. One
            # reading per tick per token keeps the request count bounded.
            pending = [a for a in OUTCOME_AGES_S if age >= a and a not in recorded]
            if pending:
                due.append((tok, min(pending)))

        if not due:
            return

        addrs = [str(t["token_address"]) for t, _ in due]
        try:
            async with DexScreenerClient() as dex:
                states = await dex.token_states(addrs)
        except Exception as exc:  # noqa: BLE001
            log.warning("outcome tracking lookup failed: %s", exc)
            return

        wrote = 0
        for tok, target_age in due:
            st = states.get(str(tok["token_address"]))
            if st is None:
                # Do NOT write a zero row. An unpriceable token must stay a gap
                # in the series, not a fabricated crash to zero.
                continue
            self.store.record_price_snapshot(
                token_address=str(tok["token_address"]),
                network_id=int(tok["network_id"]),  # type: ignore[arg-type]
                age_seconds=target_age,
                price_usd=st.price_usd,
                market_cap_usd=st.market_cap_usd,
                liquidity_usd=st.liquidity_usd,
                volume_h1_usd=st.volume_h1_usd,
                buys_m5=st.buys_m5,
                sells_m5=st.sells_m5,
            )
            wrote += 1
        if wrote:
            log.info("outcome tracking: recorded %d price snapshots", wrote)

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
