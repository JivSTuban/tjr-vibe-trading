"""Radar orchestrator: stream launches, enrich, score, alert, record.

Shape of the loop:

  PumpPortal (one socket)  ->  every create is recorded immediately
                               every create becomes a tracked candidate
  enrichment tick (5s)     ->  batch DexScreener for candidates due a snapshot
                               compute flow features, score Moon / Rug / Echo
                               decide alerts, send the loudest first
  trend tick               ->  promote matured candidates into the Trend Context

Two deliberate properties:

* Recording is unconditional. Every launch lands in the database whether or not
  it ever alerts, because PRD section 8 needs the rejects to establish a base
  rate. Without them the thresholds can never be validated, only asserted.
* Alerting is confined to the first five minutes, while snapshotting continues
  to one hour. The alert window is a product decision; the snapshot window is a
  dataset decision, and conflating them would either spam the channel or starve
  the backtest.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import time

import httpx

from .alerts import decide, sort_for_send
from .config import SNAPSHOT_AGES_SECONDS, RadarConfig, load_config
from .discord_sink import DiscordSink
from .features import compute_flow
from .models import Candidate, MarketSnapshot, utcnow
from .retention import prune as prune_cold_rows
from .scoring.moon import score_moon
from .scoring.rug import score_rug
from .scoring.trend_echo import best_match
from .sources.dexscreener import DexScreenerClient, PairState
from .sources.helius import HeliusClient, HolderConcentration, TokenAuthorities
from .sources.metadata import MetadataFetcher
from .sources.pumpportal import PumpPortalStream, parse_launch, parse_trade
from .store import Store
from .trend_context import TrendContext

log = logging.getLogger("radar")

ENRICH_TICK_S = 5.0
ALERT_WINDOW_S = 300.0  # only the first five minutes can produce a notification
CANDIDATE_MAX_AGE_S = max(SNAPSHOT_AGES_SECONDS) + 120
STATUS_EVERY_S = 60.0

# Unmanaged, the dataset grows ~150-280 MB/day at observed launch rates. Thinning
# cold never-alerted rows recovers over half of that, so it runs on a timer
# rather than waiting for someone to notice the disk.
PRUNE_EVERY_S = 6 * 3600.0

# Structural checks cost Helius credits, so they run once per candidate and only
# for tokens that have shown enough life to be worth the call.
HELIUS_MIN_MCAP_USD = 8_000.0


class Radar:
    def __init__(self, cfg: RadarConfig) -> None:
        self.cfg = cfg
        self.store = Store(cfg.db_path)
        self.trends = TrendContext()
        self.candidates: dict[str, Candidate] = {}
        self._snapshotted: dict[str, set[int]] = {}
        # Both of these are keyed by mint and must be pruned with the candidate
        # they belong to. Left unbounded they grow by ~35k-63k entries per day,
        # which is invisible in a five-minute test and a slow leak in a process
        # meant to run for weeks.
        self._helius_checked: set[str] = set()
        self._metadata_attempted: set[str] = set()
        self._authorities: dict[str, TokenAuthorities] = {}
        self._holders: dict[str, HolderConcentration] = {}
        self._smart_wallets: dict[str, float] = {}
        self._launches_seen = 0
        self._alerts_sent = 0
        self._rug_suppressed = 0
        self._started = time.monotonic()
        self._stop = asyncio.Event()
        self._bg_tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------- ingestion

    def _on_launch(self, msg: dict) -> None:
        ev = parse_launch(msg)
        if ev is None:
            return
        self._launches_seen += 1
        # Record before anything can fail downstream: the dataset is the asset.
        self.store.record_launch(ev)
        self.candidates[ev.mint] = Candidate(launch=ev)
        self._snapshotted[ev.mint] = set()

    def _on_trade(self, msg: dict) -> None:
        """Fold a trade into its candidate. Only reachable on the paid stream."""
        trade = parse_trade(msg)
        if trade is None:
            return
        cand = self.candidates.get(trade.mint)
        if cand is None:
            return
        if trade.is_buy:
            cand.buyers.add(trade.trader)
            cand.buy_count += 1
        else:
            cand.sellers.add(trade.trader)
            cand.sell_count += 1
            if trade.trader == cand.launch.creator:
                cand.creator_sold = True
        cand.sol_volume += trade.sol_amount
        if trade.is_buy and trade.trader in self._smart_wallets:
            cand.smart_wallets.add(trade.trader)
        self.store.record_trades([trade])

    def _on_migration(self, msg: dict) -> None:
        """A token graduating off the bonding curve is the strongest trend evidence."""
        mint = str(msg.get("mint") or "")
        cand = self.candidates.get(mint)
        if cand is not None:
            self.trends.consider(cand, migrated=True)
            log.info("migration: $%s promoted to trend context", cand.launch.symbol)

    async def _consume_stream(self, stream: PumpPortalStream) -> None:
        async for msg in stream.events():
            if self._stop.is_set():
                return
            tx = msg.get("txType")
            if tx == "create":
                self._on_launch(msg)
            elif tx in ("buy", "sell"):
                self._on_trade(msg)
            elif "migration" in str(msg.get("txType") or "").lower() or msg.get("pool") == "raydium":
                self._on_migration(msg)

    # ------------------------------------------------------------ enrichment

    def _due_for_snapshot(self) -> list[tuple[Candidate, int]]:
        """Candidates that have crossed a snapshot age not yet recorded."""
        due: list[tuple[Candidate, int]] = []
        for cand in self.candidates.values():
            age = cand.age_seconds
            done = self._snapshotted.setdefault(cand.mint, set())
            for target in SNAPSHOT_AGES_SECONDS:
                if age >= target and target not in done:
                    due.append((cand, target))
                    break
        return due

    async def _enrich_once(
        self, dex: DexScreenerClient, helius: HeliusClient | None, sink: DiscordSink
    ) -> None:
        due = self._due_for_snapshot()
        if not due:
            return

        sol_price = await dex.sol_price_usd()
        states = await dex.token_states([c.mint for c, _ in due])

        to_send: list[tuple[object, Candidate]] = []
        for cand, target_age in due:
            state = states.get(cand.mint)
            self._snapshotted[cand.mint].add(target_age)
            snap = self._build_snapshot(cand, state, target_age, sol_price)
            cand.snapshots.append(snap)
            self.store.record_snapshot(snap)

            # Alerting stops at five minutes; snapshots continue for the dataset.
            if cand.age_seconds > ALERT_WINDOW_S:
                self.trends.consider(cand)
                continue

            await self._maybe_structural_checks(cand, helius, snap)
            alerts = self._score_and_decide(cand, target_age)
            for alert in sort_for_send(alerts):
                to_send.append((alert, cand))

        for alert, cand in to_send:
            # Recorded unconditionally — the rejects ARE the base rate, and the
            # outcome labeller reads this table.
            alert_id = self.store.record_alert(alert)  # type: ignore[arg-type]
            if not self.cfg.post_rug_warnings and alert.alert_type == "RUG_WARNING":
                # Still stored above, just not posted. Rug warnings were 76 of
                # this radar's ~120 alerts, i.e. most of the channel was
                # warnings about tokens nobody was going to buy.
                self._rug_suppressed += 1
                continue
            delivered = await sink.send(alert, cand)  # type: ignore[arg-type]
            if delivered:
                self._alerts_sent += 1
                self.store.mark_delivered(alert_id)

    def _build_snapshot(
        self, cand: Candidate, state: PairState | None, target_age: int, sol_price: float
    ) -> MarketSnapshot:
        """Assemble a snapshot, falling back to curve maths when DexScreener is blank.

        A pair can legitimately be missing for the first seconds, and the launch
        event already carries curve state in SOL, so a missing pair degrades to a
        coarser snapshot instead of a hole in the series.
        """
        if state is not None:
            liquidity = state.liquidity_usd or cand.launch.v_sol_in_curve * sol_price
            return MarketSnapshot(
                mint=cand.mint,
                ts=utcnow(),
                age_seconds=float(target_age),
                price_usd=state.price_usd,
                market_cap_usd=state.market_cap_usd,
                liquidity_usd=liquidity,
                volume_usd=state.volume_m5_usd,
                buys=state.buys_m5,
                sells=state.sells_m5,
                unique_buyers=len(cand.buyers),
                source="dexscreener",
            )
        return MarketSnapshot(
            mint=cand.mint,
            ts=utcnow(),
            age_seconds=float(target_age),
            market_cap_usd=cand.launch.market_cap_sol * sol_price,
            liquidity_usd=cand.launch.v_sol_in_curve * sol_price,
            buys=cand.buy_count,
            sells=cand.sell_count,
            unique_buyers=len(cand.buyers),
            source="pumpportal",
        )

    async def _maybe_structural_checks(
        self, cand: Candidate, helius: HeliusClient | None, snap: MarketSnapshot
    ) -> None:
        """Run the paid-ish authority and holder checks once, on live tokens only."""
        if helius is None or cand.mint in self._helius_checked:
            return
        if snap.market_cap_usd < HELIUS_MIN_MCAP_USD:
            return
        self._helius_checked.add(cand.mint)
        auth, holders = await asyncio.gather(
            helius.authorities(cand.mint), helius.holder_concentration(cand.mint)
        )
        self._authorities[cand.mint] = auth
        self._holders[cand.mint] = holders
        if auth.available or holders.available:
            self.store.record_holders(
                cand.mint,
                utcnow(),
                holders.holder_count,
                holders.top10_pct,
                cand.launch.creator_supply_pct,
                auth.mint_authority,
                auth.freeze_authority,
            )

    def _score_and_decide(self, cand: Candidate, target_age: int) -> list:
        feat = compute_flow(cand.snapshots)
        cand.moon = score_moon(cand, feat, self._smart_wallets)
        cand.rug = score_rug(
            cand,
            feat,
            deployer_launches=self.store.deployer_launch_count(cand.launch.creator),
            deployer_rugs=self.store.deployer_rug_count(cand.launch.creator),
            authorities=self._authorities.get(cand.mint),
            holders=self._holders.get(cand.mint),
        )
        refs = self.trends.references()
        if refs:
            ref, sb = best_match(cand, refs, feat)
            cand.related_trend, cand.trend = ref, sb
        self.store.record_candidate_scores(cand, float(target_age))
        return decide(cand, self.cfg.thresholds)

    # ----------------------------------------------------------- housekeeping

    async def _fetch_metadata_soon(self, meta_fetcher: MetadataFetcher, mint: str) -> None:
        """Fetch narrative metadata off the critical path.

        IPFS took ~6.5s in testing, so this never blocks an alert; it improves
        the score at the next enrichment tick instead.

        Failures are swallowed deliberately. This runs as a detached task, and a
        gateway that times out during shutdown must not surface as an unhandled
        task exception, which is exactly what the first live run produced.
        """
        cand = self.candidates.get(mint)
        if cand is None or not cand.launch.uri:
            return
        try:
            meta = await meta_fetcher.fetch(cand.launch.uri)
        except (asyncio.CancelledError, RuntimeError):
            # Cancelled at shutdown, or the shared client closed underneath us.
            return
        except Exception:  # noqa: BLE001 - metadata is optional by design
            log.debug("metadata fetch failed for %s", mint[:8])
            return
        if meta.fetched:
            cand.metadata = meta
            self.store.update_metadata(mint, meta)

    def _spawn_metadata(self, meta_fetcher: MetadataFetcher, mint: str) -> None:
        """Start a detached metadata fetch and keep a handle so it can be cancelled.

        Without the handle these tasks outlive the HTTP client's context manager
        and raise "client has been closed" on every pending fetch at shutdown.
        """
        task = asyncio.create_task(self._fetch_metadata_soon(meta_fetcher, mint))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _drain_background(self) -> None:
        """Cancel outstanding metadata fetches before the HTTP clients close."""
        for task in list(self._bg_tasks):
            task.cancel()
        if self._bg_tasks:
            await asyncio.gather(*list(self._bg_tasks), return_exceptions=True)
        self._bg_tasks.clear()

    def _prune(self) -> None:
        """Drop every per-mint structure once a candidate ages out.

        All six maps are keyed by mint and must be cleared together. Missing one
        turns a bounded working set into a leak that only shows up after days.
        """
        stale = [m for m, c in self.candidates.items() if c.age_seconds > CANDIDATE_MAX_AGE_S]
        for mint in stale:
            self.candidates.pop(mint, None)
            self._snapshotted.pop(mint, None)
            self._authorities.pop(mint, None)
            self._holders.pop(mint, None)
            self._helius_checked.discard(mint)
            self._metadata_attempted.discard(mint)

    def working_set_size(self) -> int:
        """Total tracked entries, so a leak is observable rather than inferred."""
        return (
            len(self.candidates)
            + len(self._snapshotted)
            + len(self._authorities)
            + len(self._holders)
            + len(self._helius_checked)
            + len(self._metadata_attempted)
        )

    def _status(self) -> str:
        elapsed = max(1.0, time.monotonic() - self._started)
        rate = self._launches_seen / elapsed * 60.0
        return (
            f"{self._launches_seen} launches ({rate:.0f}/min) · "
            f"{len(self.candidates)} tracked · {len(self.trends)} trends · "
            f"{self._alerts_sent} alerts sent"
            + (
                f" · {self._rug_suppressed} rug warnings recorded not posted"
                if self._rug_suppressed
                else ""
            )
        )

    # ------------------------------------------------------------------- run

    async def run(self, duration_s: float | None = None) -> None:
        self._smart_wallets = self.store.smart_wallets()
        stream = PumpPortalStream()

        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as http,
            DexScreenerClient() as dex,
            MetadataFetcher() as meta_fetcher,
            DiscordSink(
                self.cfg.discord_webhook_url,
                max_per_min=self.cfg.max_alerts_per_min,
                max_per_hour=self.cfg.max_alerts_per_hour,
                dry_run=self.cfg.dry_run,
            ) as sink,
        ):
            helius = None
            if self.cfg.has_helius:
                helius = HeliusClient(self.cfg.helius_rpc_url, client=http)

            mode = "dry-run" if sink.dry_run else "live"
            await sink.send_startup(
                f"Mode: **{mode}** · smart-wallet list: {len(self._smart_wallets)} · "
                f"structural checks: {'on' if helius else 'off (no Helius key)'}"
            )
            log.info("radar started (%s)", mode)

            consumer = asyncio.create_task(self._consume_stream(stream))
            deadline = time.monotonic() + duration_s if duration_s else None
            last_status = time.monotonic()
            last_retention = time.monotonic()

            try:
                while not self._stop.is_set():
                    await asyncio.sleep(ENRICH_TICK_S)

                    # Kick metadata fetches for launches we have not tried yet.
                    for mint, cand in list(self.candidates.items()):
                        if mint not in self._metadata_attempted and not cand.metadata.fetched:
                            self._metadata_attempted.add(mint)
                            self._spawn_metadata(meta_fetcher, mint)

                    try:
                        await self._enrich_once(dex, helius, sink)
                    except Exception:  # noqa: BLE001 - one bad tick must not kill the radar
                        log.exception("enrichment tick failed")

                    self._prune()

                    if time.monotonic() - last_retention >= PRUNE_EVERY_S:
                        last_retention = time.monotonic()
                        try:
                            stats = prune_cold_rows(self.store)
                            log.info("retention: %s", stats.summary().replace("\n", " "))
                        except Exception:  # noqa: BLE001 - never kill the radar over disk
                            log.exception("retention pass failed")

                    if time.monotonic() - last_status >= STATUS_EVERY_S:
                        log.info("status: %s", self._status())
                        last_status = time.monotonic()

                    if deadline and time.monotonic() >= deadline:
                        break
            finally:
                consumer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await consumer
                await self._drain_background()
                log.info("radar stopped: %s", self._status())
                log.info("database: %s", self.store.counts())
                self.store.close()

    def request_stop(self) -> None:
        self._stop.set()


def _print_status(cfg: RadarConfig) -> None:
    store = Store(cfg.db_path)
    counts = store.counts()
    by_type = store.alert_counts_by_type()
    print(f"database: {cfg.db_path}")
    for table, n in counts.items():
        print(f"  {table:22s} {n:>9,}")
    if by_type:
        print("alerts by type:")
        for tier, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
            print(f"  {tier:22s} {n:>9,}")
    store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Meme Coin Alpha Radar")
    parser.add_argument("--dry-run", action="store_true",
                        help="log alerts instead of posting them to Discord")
    parser.add_argument("--duration", type=float, default=None,
                        help="stop after N seconds (for smoke tests)")
    parser.add_argument("--status", action="store_true",
                        help="print database counts and exit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(dry_run=args.dry_run)
    if args.status:
        _print_status(cfg)
        return

    if not cfg.discord_webhook_url and not cfg.dry_run:
        print(
            "No Discord webhook configured. Set RADAR_DISCORD_WEBHOOK, or store it with:\n"
            "  security add-generic-password -s radar-discord-webhook -a webhook "
            "-w '<webhook-url>'\n"
            "Running with --dry-run instead."
        )
        cfg.dry_run = True

    radar = Radar(cfg)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, radar.request_stop)
    try:
        loop.run_until_complete(radar.run(duration_s=args.duration))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
