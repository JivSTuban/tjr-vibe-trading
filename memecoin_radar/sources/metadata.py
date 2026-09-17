"""Off-chain token metadata (description, image, socials) behind the launch URI.

This is the narrative input the Trend Echo scorer wants, and it is also the
slowest thing in the pipeline. Measured on 2026-09-17: `ipfs.io` did not resolve
at all from this machine, `cloudflare-ipfs.com` refused the connection, and
`gateway.pinata.cloud` answered in ~6.5 seconds.

Six seconds against a sub-minute alert budget means metadata must never block a
notification. The fetch runs opportunistically with a short timeout; if it is not
back in time the alert goes out with on-chain evidence only, and the +1m/+3m/+5m
enrichment fills in the narrative for the follow-up.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from ..models import TokenMetadata

log = logging.getLogger(__name__)

# Ordered by measured reliability from this network, not by popularity.
IPFS_GATEWAYS = (
    "https://gateway.pinata.cloud/ipfs/",
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
)

_CID_RE = re.compile(r"/ipfs/([A-Za-z0-9]+)")

# Per-gateway timeout. Short on purpose: trying a second gateway quickly beats
# waiting on a slow one, because the alert clock is running.
GATEWAY_TIMEOUT_S = 4.0


def extract_cid(uri: str) -> str:
    """Pull the CID out of a gateway URL or an ipfs:// URI."""
    if not uri:
        return ""
    if uri.startswith("ipfs://"):
        return uri[len("ipfs://") :].strip("/")
    m = _CID_RE.search(uri)
    return m.group(1) if m else ""


def parse_metadata(doc: dict[str, Any]) -> TokenMetadata:
    """Map a pump.fun metadata document onto TokenMetadata.

    Field names verified against live documents: name, symbol, description,
    image, showName, createdOn, plus twitter/telegram/website when the creator
    supplied them.
    """
    return TokenMetadata(
        description=str(doc.get("description") or "").strip(),
        image=str(doc.get("image") or "").strip(),
        twitter=str(doc.get("twitter") or "").strip(),
        telegram=str(doc.get("telegram") or "").strip(),
        website=str(doc.get("website") or "").strip(),
        fetched=True,
    )


class MetadataFetcher:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None
        self._cache: dict[str, TokenMetadata] = {}

    async def __aenter__(self) -> MetadataFetcher:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(GATEWAY_TIMEOUT_S, connect=2.0),
                follow_redirects=True,
                headers={"accept": "application/json"},
            )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, uri: str) -> TokenMetadata:
        """Best-effort metadata fetch, trying gateways in order.

        Always returns a TokenMetadata; `fetched=False` means every gateway
        failed and the narrative components must be treated as unavailable
        rather than as empty strings that happen to score zero.
        """
        cid = extract_cid(uri)
        if not cid:
            return TokenMetadata()
        if cid in self._cache:
            return self._cache[cid]
        assert self._client is not None, "use MetadataFetcher as an async context manager"

        for gateway in IPFS_GATEWAYS:
            try:
                resp = await self._client.get(f"{gateway}{cid}")
            except (httpx.HTTPError, asyncio.TimeoutError):
                continue
            if resp.status_code != 200:
                continue
            try:
                doc = resp.json()
            except ValueError:
                continue
            if isinstance(doc, dict):
                meta = parse_metadata(doc)
                self._cache[cid] = meta
                return meta
        log.debug("metadata unavailable for %s", cid)
        return TokenMetadata()
