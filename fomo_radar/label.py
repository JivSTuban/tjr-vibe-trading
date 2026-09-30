"""Label alerted tokens into `fomo_outcomes`.

    uv run python -m fomo_radar.label                 # label what is settled
    uv run python -m fomo_radar.label --min-age 3600  # require 1h of forward data
    uv run python -m fomo_radar.label --report        # print, write nothing

Why this exists
---------------
Every threshold in `signal.py` is a measured *ordering* on a survivorship-biased
sample, not a validated hit rate. `fomo_outcomes` is the table that would turn
one into the other, and it sat at 0 rows for three sessions while the signal was
rewritten twice. Nothing about the entry gate is validated until this has run
against real forward prices.

Labelling reuses `memecoin_radar.backtest.label_one` unchanged. It is already
generic over a list of dicts, and a second implementation of "what happened
next" is exactly how two packages end up disagreeing about the same trade.

The control group is the point
-----------------------------
Suppressed alerts are labelled too (`include_suppressed=True`). The ENTER NOW
gate refuses far more than it delivers, so if it is throwing away winners, the
ONLY place that shows up is a comparison between what it entered and what it
refused. Labelling only the delivered alerts would make the gate unfalsifiable
by construction.
"""

from __future__ import annotations

import argparse
import logging

from memecoin_radar.backtest import is_pair_flip, label_one

from .config import SignalConfig, load_config
from .store import FomoStore

log = logging.getLogger("fomo_radar.label")

# A token needs at least this much forward history before its outcome means
# anything. The first return window is 1h, and `label_one` already returns None
# for windows it cannot cover, so this only avoids pointless work.
MIN_AGE_S = 3600.0


def label_all(store: FomoStore, *, min_age_s: float = MIN_AGE_S,
              dry_run: bool = False, max_price_usd: float | None = None) -> dict[str, int]:
    """Label every alerted token with enough forward data. Returns a tally."""
    if max_price_usd is None:
        max_price_usd = SignalConfig().max_price_usd
    tally = {"considered": 0, "labelled": 0, "too_thin": 0, "pair_flip": 0,
             "wrapped_asset": 0, "unlabelled": 0, "entered": 0, "suppressed": 0}

    for row in store.alerted_tokens(include_suppressed=True):
        tally["considered"] += 1
        token = str(row["token_address"])
        network = int(row["network_id"])  # type: ignore[arg-type]
        series = store.price_series(token, network)

        # `label_one` needs two usable points; requiring the series to REACH
        # min_age_s is what makes the label settled rather than merely present.
        if not series or max(float(s["age_seconds"]) for s in series) < min_age_s:
            tally["too_thin"] += 1
            continue

        # Screen BEFORE labelling. `label_one` measures returns off
        # `market_cap_usd`, which is the field a pair flip corrupts, so a mixed
        # series produces a fabricated multi-hundred-x that swamps every real
        # row. The first run of this labeller (2026-09-17) labelled 18 tokens
        # and NVDAX came back at +18,605% on a price that moved 0.4%.
        # Screen out tokenised real-world assets. `SignalConfig.max_price_usd`
        # stops new ones being ALERTED, but this table already held 8 of them
        # out of 12 rows (MSFTX, GLDX, CRCLX, SPYX, GOOGLX, SPCXx, EURC,
        # tOpenAI), and a median computed across those describes an equity
        # tracker rather than a meme coin. Gating only the alert path would
        # leave the contamination in place for whoever queries this next.
        if max_price_usd > 0 and any(
            float(s.get("price_usd") or 0) > max_price_usd for s in series
        ):
            tally["wrapped_asset"] += 1
            if not dry_run and store.delete_outcome(token, network):
                tally["unlabelled"] += 1
            continue

        if is_pair_flip(series):
            tally["pair_flip"] += 1
            # Skipping is not enough: a row labelled before this screen existed
            # would otherwise survive every future run untouched.
            if not dry_run and store.delete_outcome(token, network):
                tally["unlabelled"] += 1
            continue

        outcome = label_one(series)
        if outcome is None:
            tally["too_thin"] += 1
            continue

        entry = next(
            (s for s in series if (s.get("market_cap_usd") or 0) > 0), None
        )
        entry_liq = float(entry.get("liquidity_usd") or 0.0) if entry else 0.0

        if not dry_run:
            store.record_outcome(
                token_address=token,
                network_id=network,
                ticker=str(row.get("ticker") or "?"),
                tier=row.get("tier"),  # type: ignore[arg-type]
                score=float(row.get("score") or 0.0),
                alerted_at=str(row.get("first_alert") or ""),
                entry_mcap_usd=outcome.entry_mcap_usd,
                entry_liquidity_usd=entry_liq,
                returns=outcome.returns,
                max_drawdown=outcome.max_drawdown,
                rugged=outcome.rugged,
                times=outcome.times_to_multiple,
            )
        tally["labelled"] += 1
        tally["entered" if row.get("entered") else "suppressed"] += 1

    if not dry_run:
        store.conn.commit()
    return tally


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-age", type=float, default=MIN_AGE_S,
                    help="seconds of forward history required (default 3600)")
    ap.add_argument("--report", action="store_true",
                    help="label nothing; just print what would be written")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    store = FomoStore(cfg.db_path)
    try:
        tally = label_all(store, min_age_s=args.min_age, dry_run=args.report)
        log.info(
            "%s %d of %d alerted tokens (%d entered / %d suppressed); "
            "%d lacked %.0fs of forward data; %d dropped as pair-flip corrupt "
            "(%d wrapped assets, %d stale bad rows removed)",
            "would label" if args.report else "labelled",
            tally["labelled"], tally["considered"], tally["entered"],
            tally["suppressed"], tally["too_thin"], args.min_age,
            tally["pair_flip"], tally["wrapped_asset"], tally["unlabelled"],
        )
        # A zero here is the honest headline, not a quiet success: it means
        # nothing in this repo is validated yet.
        if tally["labelled"] == 0:
            log.info(
                "fomo_outcomes gained NOTHING — no alerted token has %.0fs of "
                "forward prices yet, so no signal here is validated.",
                args.min_age,
            )
    finally:
        store.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
