"""Configuration for the fomo social-signal harvester.

Secrets resolve from the environment first, then the macOS keychain, matching
`memecoin_radar.config`. Env wins so a one-off run can point at a scratch DB or
a test channel without touching stored credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from memecoin_radar.config import _keychain

# fomo's Privy application id, read off the live app's auth calls. Not a secret
# (it ships in the client bundle) but it is required on every token refresh.
PRIVY_APP_ID = "cm6h485o300n3zj9yl6vpedq7"
PRIVY_SESSIONS_URL = "https://auth.privy.io/api/v1/sessions"
PRIVY_CLIENT = "react-auth:2.32.0"

API_BASE = "https://prod-api.fomo.family"
APP_ORIGIN = "https://fomo.family"

# Chain ids the app advertises. Sent on every request as `x-supported-chains`;
# omitting it returns partial data for multi-chain feed items.
SUPPORTED_CHAINS = "1,56,143,4663,5042,8453,1399811149"
SOLANA_NETWORK_ID = 1399811149

DEFAULT_DB_PATH = Path.home() / "memecoin-radar-data" / "radar.sqlite3"


@dataclass
class SignalConfig:
    """Gates for the social-conviction signal.

    Every value here is grounded in `research/fomo/FINDINGS.md`, measured over
    20,337 theses across 50 trending tokens on 2026-09-17. Read the caveat in
    that document before tuning any of them: the sample is survivorship-biased
    (trending tokens only), so the *ordering* of these cuts is evidence and the
    absolute PnL levels behind them are not.
    """

    # Theses below this size are noise. fomo's own UI defaults to the same
    # $1,000 gate. Measured: median size of a thesis carrying an X link is
    # $5,086 vs $655 for one without, and essentially the whole apparent
    # "X link edge" is that size difference.
    min_thesis_usd: float = 1000.0

    # Earliness is the signal that survived. Median unrealized PnL decays
    # monotonically across all ten deciles of thesis order on a token, +192% for
    # the earliest 10% down to +21% for the latest 10%. We alert only inside the
    # front of that curve.
    max_thesis_rank: int = 10

    # A single author can post repeatedly on one token (observed: the same
    # handle three times in four minutes). Distinct authors is the real
    # confirmation, so alerting requires more than one.
    min_distinct_authors: int = 2

    # A leaderboard author is a quality marker, not a discovery one: the
    # leaderboard's own top-consensus holdings are already-won positions, so
    # this raises a candidate's tier but can never create one on its own.
    leaderboard_bonus_tier: bool = True

    # Deliberately NOT a gate: the presence of an x.com link. It reads as a
    # strong filter raw (win 57.1% vs 46.0%) but that is a size proxy, and above
    # $5k it inverts (X +108.7% vs no-link +117.9%). Stored, never scored.
    # See FINDINGS.md "The X link is not the signal".


@dataclass
class FomoConfig:
    """Everything the harvester needs, resolved from the environment."""

    privy_refresh_token: str = ""
    discord_webhook_url: str = ""
    db_path: Path = DEFAULT_DB_PATH
    signal: SignalConfig = field(default_factory=SignalConfig)

    # The global feed is a 25-item non-paginated window. Anything that scrolls
    # off between polls is gone for good, so the interval is set from the
    # observed fill rate rather than politeness: during the 2026-09-17 sample the
    # window turned over roughly every 80 minutes at threshold=1000, but bursts
    # are far faster. 20s keeps a wide margin without hammering the API.
    poll_interval_s: float = 20.0

    # The access token lives one hour. Refresh early so a slow refresh never
    # lands after expiry mid-poll.
    token_refresh_margin_s: float = 600.0

    # The leaderboard changes on a daily cadence, not a per-minute one.
    leaderboard_interval_s: float = 6 * 3600.0

    headless: bool = False  # headless is BLOCKED by fomo's edge; see session.py
    dry_run: bool = False

    max_alerts_per_min: int = 4
    max_alerts_per_hour: int = 20


def load_config(dry_run: bool = False) -> FomoConfig:
    """Resolve config from env first, then the keychain."""
    refresh = os.environ.get("FOMO_REFRESH_TOKEN", "") or _keychain(
        "fomo-privy-refresh", "refresh-token"
    )
    webhook = os.environ.get("FOMO_DISCORD_WEBHOOK", "") or os.environ.get(
        "RADAR_DISCORD_WEBHOOK", ""
    ) or _keychain("radar-discord-webhook", "webhook")
    db = Path(os.environ.get("RADAR_DB_PATH", str(DEFAULT_DB_PATH)))
    return FomoConfig(
        privy_refresh_token=refresh.strip(),
        discord_webhook_url=webhook.strip(),
        db_path=db,
        dry_run=dry_run,
    )
