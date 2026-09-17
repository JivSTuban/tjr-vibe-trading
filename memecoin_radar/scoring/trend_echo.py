"""Trend Relation Score, PRD section 4.3: is this launch a derivative of a live trend.

The PRD is explicit that this score must never imply safety. A clone is at least
as likely to be impersonation as it is to be the next leg of a narrative, so
relation raises discovery priority only, and the Rug score keeps its independent
veto. That separation is enforced in `alerts.py`, not here.

Similarity uses difflib from the standard library rather than a fuzzy-match
dependency: the strings are short (a name and a ticker), the volume is ~24/min,
and a new third-party package for this would not earn its place.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..features import FlowFeatures
from ..models import Candidate, ScoreBreakdown, TrendReference
from . import clamp, saturating, weighted_score

WEIGHTS: dict[str, float] = {
    "name_ticker": 0.22,
    "narrative": 0.18,
    "image_logo": 0.15,
    "keyword_entity": 0.10,
    "social_reference": 0.10,
    "creator_relationship": 0.10,
    "launch_timing": 0.10,
    "early_buyer_momentum": 0.05,
}

_WORD_RE = re.compile(r"[a-z0-9]+")

# Meme tickers are dominated by these, so they carry no narrative information
# and would otherwise make every launch look related to every other launch.
STOPWORDS = frozenset(
    """
    the a an and or of to in on for with is it this that coin token meme
    official real new solana sol pump fun community memecoin crypto
    """.split()
)

# Clone prefixes and suffixes: the literal mechanic the Echo radar exists to catch.
CLONE_AFFIXES = ("baby", "mini", "big", "super", "mega", "king", "queen", "lil",
                 "little", "daddy", "mama", "papa", "2", "ii", "x", "inu", "jr")


def normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def tokenize(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in STOPWORDS and len(w) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap(a: set[str], b: set[str]) -> float:
    """Overlap coefficient: intersection over the SMALLER set.

    Used for entity overlap rather than Jaccard because the question there is
    containment, not mutual similarity. A clone named "Baby Frog BABYFROG"
    carries the trend's entity "frog" completely, but Jaccard would score that
    at 0.33 purely because the clone added tokens of its own, which penalises
    exactly the naming pattern the Echo radar exists to detect.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def string_similarity(a: str, b: str) -> float:
    """0-100 similarity for short names and tickers.

    Containment is treated as a strong match on purpose. "BABYFROG" against
    "FROG" is the canonical clone shape from the PRD's own example, and plain
    edit-distance scores it only moderately because of the added prefix.
    """
    a_n, b_n = normalize(a), normalize(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 100.0

    ratio = SequenceMatcher(None, a_n, b_n).ratio() * 100.0

    short, long = (a_n, b_n) if len(a_n) <= len(b_n) else (b_n, a_n)
    if len(short) >= 3 and short in long:
        # Scale with how much of the longer string the shared root explains, so
        # "FROG" inside "FROG" beats "FROG" inside a long unrelated sentence.
        coverage = len(short) / len(long)
        affix = long.replace(short, "", 1).strip()
        # A recognised clone affix is the strongest naming evidence there is:
        # someone deliberately built "BABY" + an existing ticker.
        affix_bonus = 20.0 if affix in CLONE_AFFIXES else 0.0
        ratio = max(ratio, clamp(55.0 + 35.0 * coverage + affix_bonus))
    return clamp(ratio)


def _timing_score(cand: Candidate, ref: TrendReference) -> float:
    """How close this launch is to the reference trend still being live.

    Peaks while the reference is accelerating and decays as it cools, because a
    clone of a trend that already topped is a different and much worse trade
    than a clone of one still climbing.
    """
    age_min = max(0.0, (cand.launch.seen_at - ref.first_seen).total_seconds() / 60.0)
    state_ceiling = {
        "accelerating": 100.0,
        "emerging": 85.0,
        "peak": 60.0,
        "cooling": 25.0,
    }.get(ref.momentum_state, 50.0)
    # Full marks within the first 30 minutes of the trend, decaying to zero by 6h.
    decay = clamp(100.0 * (1.0 - max(0.0, age_min - 30.0) / 330.0))
    return min(state_ceiling, decay)


def score_trend_relation(
    cand: Candidate, ref: TrendReference, feat: FlowFeatures
) -> ScoreBreakdown:
    reasons: list[str] = []

    name_sim = max(
        string_similarity(cand.launch.name, ref.name),
        string_similarity(cand.launch.symbol, ref.symbol),
    )
    if name_sim >= 70.0:
        reasons.append(f"name/ticker echoes ${ref.symbol} ({name_sim:.0f}/100)")

    if cand.metadata.fetched and ref.narrative_tokens:
        cand_tokens = tokenize(cand.metadata.description) | tokenize(cand.launch.name)
        narrative: float | None = jaccard(cand_tokens, ref.narrative_tokens) * 100.0
        if narrative and narrative >= 40.0:
            reasons.append("description shares the trend's narrative language")
    else:
        narrative = None

    # Image similarity needs a CLIP-style embedding model, PRD Phase 4.
    image: float | None = None

    if ref.keywords:
        keyword: float | None = overlap(
            tokenize(f"{cand.launch.name} {cand.launch.symbol}"), ref.keywords
        ) * 100.0
    else:
        keyword = None

    # Social overlap is measurable only when the launch declared socials at all.
    # A token with no links is unmeasured, not disproven: scoring it zero would
    # penalise the many legitimate launches that add socials minutes later.
    social: float | None = None
    if cand.metadata.fetched:
        cand_socials = {
            s.lower().rstrip("/")
            for s in (cand.metadata.twitter, cand.metadata.telegram, cand.metadata.website)
            if s
        }
        if cand_socials:
            ref_tokens = {ref.name.lower(), ref.symbol.lower()}
            hit = any(any(t and t in s for t in ref_tokens) for s in cand_socials)
            social = 100.0 if hit else 0.0
            if hit:
                reasons.append("socials reference the trend directly")

    # Same-deployer is provable; "related via a funding cluster" is not, until
    # the PRD's Phase 2 wallet-graph exists. A different deployer therefore means
    # unknown rather than unrelated, because most real clones are launched by
    # someone else entirely, and scoring that zero would suppress the signal.
    same_creator = bool(ref.creator) and cand.launch.creator == ref.creator
    creator: float | None = 100.0 if same_creator else None
    if same_creator:
        reasons.append("same deployer as the trending token")

    timing = _timing_score(cand, ref)

    momentum: float | None = (
        saturating(feat.buy_tx_rate_per_min, 20.0) if feat.samples >= 2 else None
    )

    return weighted_score(
        WEIGHTS,
        {
            "name_ticker": name_sim,
            "narrative": narrative,
            "image_logo": image,
            "keyword_entity": keyword,
            "social_reference": social,
            "creator_relationship": creator,
            "launch_timing": timing,
            "early_buyer_momentum": momentum,
        },
        reasons=reasons,
    )


def best_match(
    cand: Candidate, refs: list[TrendReference], feat: FlowFeatures
) -> tuple[TrendReference | None, ScoreBreakdown | None]:
    """Score the launch against every live trend and keep the strongest link."""
    best_ref: TrendReference | None = None
    best_sb: ScoreBreakdown | None = None
    for ref in refs:
        if ref.mint == cand.mint:
            continue
        sb = score_trend_relation(cand, ref, feat)
        if best_sb is None or sb.score > best_sb.score:
            best_ref, best_sb = ref, sb
    return best_ref, best_sb
