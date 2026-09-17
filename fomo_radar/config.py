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

    # --- earliness: the only entry-clean feature with measured support ----
    # ABSOLUTE thesis rank. A token is a candidate only while fewer than this
    # many theses exist on it. Measured per (author, token) pair, outcome being
    # that author's eventual PnL:
    #
    #     rank 0 (first ever)  n=  11  med +715.6%  win 90.9%
    #     ranks 1-4            n=  42  med +151.2%  win 78.6%
    #     ranks 5-19           n= 136  med +122.9%  win 80.9%
    #     ranks 20-99          n= 431  med  +50.3%  win 68.4%
    #     ranks 100-299        n= 905  med   +7.3%  win 52.9%
    #     ranks 300+           n= 836  med   +0.1%  win 50.2%
    #
    # against a +10.9% / 57.1% baseline. The edge is gone by rank 100, which is
    # why the $CATE alert at rank ~400 was a trophy rather than a signal.
    #
    # NOT normalised by the token's eventual thesis count. v2 used
    # first_rank/total, and `total` is future information — one of the two
    # look-ahead features that made v2 describe winners instead of finding them.
    max_thesis_rank: int = 20

    # Deliberately absent: any gate on how MANY theses one author has posted.
    # v2 gated on >=6 and it was circular — cadence accumulates only because the
    # token ran, and within the qualified population it carried rho=-0.002
    # against the author's own PnL. See signal.py's docstring.

    # --- liquidity: the "is anyone actually buying this" gate --------------
    # New in v2 and the direct fix for alerting on coins with no buyers. For
    # scale, the 50 trending tokens in the sample had a MINIMUM of $280k 24h
    # volume and 260 holders; these floors sit far below that, so they reject
    # dead tokens without pruning the real universe. Absent data fails the gate
    # rather than scoring as zero.
    min_liquidity_usd: float = 20_000.0
    min_volume_h1_usd: float = 10_000.0
    min_txns_m5: int = 1

    # A leaderboard author is a quality marker, not a discovery one: the
    # leaderboard's own top-consensus holdings are already-won positions, so
    # this raises a candidate's tier but can never create one on its own.
    # Verified the hard way: starcatcher444 was running the ALLINU thesis that
    # motivated this whole redesign and was NOT in the 24h top-150, because that
    # board ranks REALIZED PnL and a conviction holder has not sold.
    leaderboard_bonus_tier: bool = True

    # Re-alert on a genuine tier upgrade (WATCH -> HOT -> CONVICTION) rather
    # than once per token forever. A cluster that doubles is new information;
    # v1's alert-once rule meant the strongest version of a signal was the one
    # we were guaranteed to suppress.
    realert_on_upgrade: bool = True

    # Deliberately NOT a gate: the presence of an x.com link. It reads as a
    # strong filter raw (win 57.1% vs 46.0%) but that is a size proxy, and above
    # $5k it inverts (X +108.7% vs no-link +117.9%). Stored, never scored.
    # See FINDINGS.md "The X link is not the signal".
    #
    # Also deliberately NOT a gate: the dev flag. Seven dev theses exist in the
    # 20,337-thesis sample, median -40.1%, zero winners. There is no evidence
    # for "developer backed" as a positive, and n=7 cannot support one.


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
