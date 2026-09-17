"""Runtime configuration and the alert thresholds.

Thresholds are the PRD's section 5 defaults, kept in one place and labelled as
unearned: they are heuristics chosen before any outcome data exists. `backtest.py`
recomputes what they should be once the dataset has grown, which is the whole
reason every candidate is persisted rather than only the alerted ones.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PACKAGE_DIR / "data" / "radar.sqlite3"

PUMPPORTAL_WS_URL = "wss://pumpportal.fun/api/data"
DEXSCREENER_BASE = "https://api.dexscreener.com"
HELIUS_BASE = "https://mainnet.helius-rpc.com"

# Measured live on 2026-09-17: ~24 creations/min, ~34k/day. Every threshold here
# is a filter against that firehose, and Discord accepts ~30 msg/min per webhook,
# so the passing rate has to stay far below 1% of launches.
OBSERVED_LAUNCHES_PER_MIN = 24.0

# Enrichment ages from PRD sections 2.2 and 4.2.
ENRICH_AGES_SECONDS = (60, 180, 300)

# Dataset snapshot ages from PRD section 8. Deliberately separate from the
# enrichment schedule: these exist to label outcomes later, not to drive an
# alert now.
SNAPSHOT_AGES_SECONDS = (15, 30, 60, 180, 300, 600, 1800, 3600)


@dataclass(frozen=True)
class Thresholds:
    """Alert gates.

    NOT the PRD's section 5 numbers, and that is deliberate. Measured against the
    real score distribution on 2026-09-17 (169 scored tokens, ~34 launches/min),
    the PRD's gates cost:

        WATCH  > 60   ~256 alerts/hour
        HOT    > 72   ~188 alerts/hour
        ULTRA  > 84    ~60 alerts/hour

    A Discord channel carries roughly 30 useful alerts/hour, so every PRD tier
    floods it. The measured tail instead gives:

        moon > 84     4.14% of launches   ~85/hour
        moon > 86     0.59% of launches   ~12/hour
        moon > 88     none in sample

    So WATCH sits at 86 for roughly 12 alerts/hour, with the louder tiers above
    it. These are PROVISIONAL: two samples hours apart moved p90 from 73.9 to
    78.3, which is exactly why they are not treated as a result. Re-derive with
    `python -m memecoin_radar.calibrate` once the database covers enough hours.

    Sanity check that the scale is not broken: a synthetic exceptional launch
    scores 90.7 and a stronger one 94.2, so HOT and ULTRA are reachable rather
    than decorative. `test_reachability.py` enforces that.
    """

    watch_moon: float = 86.0
    watch_rug_max: float = 55.0
    hot_moon: float = 89.0
    hot_rug_max: float = 40.0
    ultra_moon: float = 93.0
    ultra_rug_max: float = 30.0
    # PRD section 5 says 80, and its own worked example ($BABYFROG against a
    # live $FROG) does not reach it with these sub-scorers: 74.8 with no
    # socials, 78.2 when the socials reference the trend. At 80 the canonical
    # case the Echo radar was built for would have been silently rejected.
    # 72 fires on both, while a clone whose socials point elsewhere (64.9) and
    # an unrelated launch (under 45) still do not.
    trend_echo_relation: float = 72.0
    rug_warning: float = 70.0
    smart_money_wallets: int = 2

    # Minimum early activity a trend clone needs before it is worth a ping.
    # Without this, TREND_ECHO fires on every name-alike with zero buyers, which
    # at 24 launches/min is pure spam.
    # Minimum early activity a trend clone needs before it earns a ping.
    # Expressed in what the FREE path can actually observe: DexScreener's
    # 5-minute buy count and USD volume. These previously read the trade-stream
    # counters, which only the metered PumpPortal stream populates, so the floor
    # was unsatisfiable and TREND_ECHO could never fire on a free deployment.
    trend_echo_min_buys: int = 5
    trend_echo_min_volume_usd: float = 300.0

    # A score built from very little measurable evidence is not comparable to a
    # fully covered one, so low-coverage candidates cannot reach the loud tiers.
    #
    # These must stay BELOW the maximum coverage actually achievable today, or
    # the tier becomes unreachable and the radar silently never escalates. In
    # Phase 1 the measurable Moon weight sums to 0.50 (volume acceleration 0.20,
    # buyer acceleration 0.15, liquidity 0.05, narrative 0.05, early entry 0.05);
    # smart money, social, cross-platform, and holder growth all need later
    # phases. `test_thresholds_are_reachable` enforces this relationship, so
    # raising a gate without shipping the data source that feeds it fails loudly.
    # Floor for ANY upside alert. Caught live on 2026-09-17: a token 18 seconds
    # old with zero buys and no volume posted "Moon 95/100 (5% evidence)",
    # because early-entry (weight 0.05) was the only measurable component and it
    # scored 95 for the unremarkable fact that a brand-new token has a small
    # market cap. Renormalizing turned one trivial component into a 95.
    # Coverage gating only guarded HOT and ULTRA, so WATCH published it.
    min_coverage_alert: float = 0.30
    min_coverage_hot: float = 0.40
    min_coverage_ultra: float = 0.48


@dataclass
class RadarConfig:
    """Everything the radar needs to run, resolved from the environment."""

    discord_webhook_url: str = ""
    helius_api_key: str = ""
    db_path: Path = DEFAULT_DB_PATH
    thresholds: Thresholds = field(default_factory=Thresholds)

    # Hard ceiling on outbound Discord traffic, independent of the score gates.
    # Discord's own limits are 5 requests/5s per channel and ~30/min per webhook;
    # staying well under both leaves headroom and keeps the channel readable.
    max_alerts_per_min: int = 6
    max_alerts_per_hour: int = 40

    # Candidates are dropped from memory once they age past the last enrichment
    # window, so the tracker does not grow without bound on a 34k/day stream.
    candidate_ttl_seconds: int = 900

    dry_run: bool = False

    @property
    def helius_rpc_url(self) -> str:
        return f"{HELIUS_BASE}/?api-key={self.helius_api_key}"

    @property
    def has_helius(self) -> bool:
        return bool(self.helius_api_key)


def _keychain(service: str, account: str = "") -> str:
    """Read a secret from the macOS keychain, the project's credential store.

    Returns empty string rather than raising: a missing Helius key degrades the
    radar to on-curve signals only, which is a supported mode, not a failure.
    """
    cmd = ["security", "find-generic-password", "-s", service, "-w"]
    if account:
        cmd[2:2] = ["-a", account]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def load_config(dry_run: bool = False) -> RadarConfig:
    """Resolve config from env first, then the keychain.

    Env wins so a one-off run can point at a test channel without touching
    stored credentials.
    """
    webhook = os.environ.get("RADAR_DISCORD_WEBHOOK", "") or _keychain(
        "radar-discord-webhook", "webhook"
    )
    helius = os.environ.get("HELIUS_API_KEY", "") or _keychain("radar-helius", "api-key")
    db = Path(os.environ.get("RADAR_DB_PATH", str(DEFAULT_DB_PATH)))
    return RadarConfig(
        discord_webhook_url=webhook.strip(),
        helius_api_key=helius.strip(),
        db_path=db,
        dry_run=dry_run,
    )
