"""Authenticated access to fomo's private API.

Why this drives a real browser instead of httpx
-----------------------------------------------
fomo's edge fingerprints the client, not the credentials. Measured 2026-09-17
with one valid access token held constant:

    curl, full browser headers          -> 430 {"error":"unauthorized"}
    node fetch, full browser headers    -> 430 {"error":"unauthorized"}
    Chromium headless=True, in-page     -> request never leaves the browser
    Chromium headless=False, in-page    -> 200

So the harvester keeps a headed Chromium open and issues every request from
inside a `fomo.family` page. `headless` is kept in the config purely so the
failure is explicit if someone flips it; it does not work.

Why no browser profile / no stored login
----------------------------------------
Privy's refresh token is accepted repeatedly and is NOT rotated (verified: two
consecutive refreshes with the same token both returned 200, and the response
body carries no replacement `refresh_token`). That means one stored secret is
enough and the browser can run from a throwaway profile, so there is no login
state to migrate between machines or keep alive.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from .config import (
    API_BASE,
    APP_ORIGIN,
    PRIVY_APP_ID,
    PRIVY_CLIENT,
    PRIVY_SESSIONS_URL,
    SUPPORTED_CHAINS,
    FomoConfig,
)

log = logging.getLogger("fomo_radar.session")


class AuthError(RuntimeError):
    """Raised when the stored refresh token no longer mints access tokens."""


class RateLimited(RuntimeError):
    """Raised on a 429 from fomo's Cloudflare edge.

    Tripped for real on 2026-09-17 by running a second session alongside the
    daemon and issuing four threshold probes back to back. The response is a
    Cloudflare "Access denied" HTML page, not JSON, so without this the caller
    sees a generic parse failure and keeps polling into the block. The feed is a
    25-item window with no pagination, so polling through a rate limit silently
    loses everything that scrolls past.
    """


# Executed inside the page. Returns the parsed body plus the HTTP status so the
# caller can distinguish "fomo said no" from "the fetch never completed".
_FETCH_JS = """
async ({ url, token, method, body }) => {
  const headers = {
    'authorization': 'Bearer ' + token,
    'content-type': 'application/json',
    'app-language': 'en',
    'x-supported-chains': %r,
  };
  try {
    const res = await fetch(url, { method, headers, body: body ?? undefined });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch (e) { /* non-JSON error page */ }
    return { status: res.status, json: parsed, text: parsed ? null : text.slice(0, 400) };
  } catch (e) {
    return { status: 0, json: null, text: String(e).slice(0, 200) };
  }
}
""" % SUPPORTED_CHAINS


_REFRESH_JS = """
async ({ url, appId, client, refresh }) => {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'privy-app-id': appId, 'privy-client': client },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  const text = await res.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch (e) {}
  return { status: res.status, token: parsed?.token ?? null, text: parsed ? null : text.slice(0, 300) };
}
"""


def _jwt_expiry(token: str) -> float:
    """Read `exp` out of a JWT without verifying it.

    We only need the clock, not trust: the token came from Privy over TLS in
    this process, and the API is the thing that actually validates it.
    """
    import base64

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, KeyError, ValueError, TypeError):
        # An unreadable token is treated as already expired so the next call
        # refreshes rather than failing on a malformed header.
        return 0.0


class FomoSession:
    """A headed browser page that can call fomo's API as the signed-in user."""

    def __init__(self, cfg: FomoConfig) -> None:
        self.cfg = cfg
        self._pw: Any = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._token: str = ""
        self._token_exp: float = 0.0

    async def __aenter__(self) -> FomoSession:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.cfg.headless)
        self._page = await self._browser.new_page()
        # The origin matters: requests are issued from this page, so it must be
        # a fomo.family document for the API's CORS and referer checks to pass.
        await self._page.goto(APP_ORIGIN, wait_until="domcontentloaded")
        await self._refresh_token()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()
        self._browser = self._page = self._pw = None

    async def _refresh_token(self) -> None:
        if self._page is None:
            raise AuthError("session is not open")
        if not self.cfg.privy_refresh_token:
            raise AuthError(
                "no Privy refresh token; set FOMO_REFRESH_TOKEN or the "
                "'fomo-privy-refresh' keychain item"
            )
        res = await self._page.evaluate(
            _REFRESH_JS,
            {
                "url": PRIVY_SESSIONS_URL,
                "appId": PRIVY_APP_ID,
                "client": PRIVY_CLIENT,
                "refresh": self.cfg.privy_refresh_token,
            },
        )
        if res.get("status") != 200 or not res.get("token"):
            raise AuthError(
                f"Privy refresh failed (status={res.get('status')}): {res.get('text')}. "
                "The stored refresh token is dead — sign in to fomo again and "
                "re-store it."
            )
        self._token = res["token"]
        self._token_exp = _jwt_expiry(self._token)
        log.info("minted access token, %.0fs of life", self._token_exp - time.time())

    async def _ensure_token(self) -> None:
        if time.time() >= self._token_exp - self.cfg.token_refresh_margin_s:
            await self._refresh_token()

    async def get(self, path: str, **params: Any) -> Any:
        """GET a fomo API path, returning `responseObject`.

        Raises on anything that is not a 200 so a silently-empty feed can never
        be mistaken for a quiet market — the failure mode this repo has been
        bitten by repeatedly.
        """
        return await self._request("GET", path, params=params)

    async def post(self, path: str, body: Any = None) -> Any:
        return await self._request("POST", path, body=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        await self._ensure_token()
        if self._page is None:
            raise AuthError("session is not open")

        url = f"{API_BASE}/{path.lstrip('/')}"
        if params:
            from urllib.parse import urlencode

            clean = {k: v for k, v in params.items() if v is not None}
            url = f"{url}?{urlencode(clean)}"

        res = await self._page.evaluate(
            _FETCH_JS,
            {
                "url": url,
                "token": self._token,
                "method": method,
                "body": json.dumps(body) if body is not None else None,
            },
        )
        status = res.get("status")
        if status == 401:
            # Token died early; mint one and retry exactly once.
            await self._refresh_token()
            res = await self._page.evaluate(
                _FETCH_JS,
                {
                    "url": url,
                    "token": self._token,
                    "method": method,
                    "body": json.dumps(body) if body is not None else None,
                },
            )
            status = res.get("status")
        if status == 429:
            raise RateLimited(
                f"fomo {method} {path} -> 429 (Cloudflare). Back off; do not "
                "keep polling into the block."
            )
        if status != 200:
            raise RuntimeError(
                f"fomo {method} {path} -> {status}: {res.get('text')}. "
                "430/431 with a valid token means the client fingerprint was "
                "rejected — check the browser is headed."
            )
        payload = res.get("json") or {}
        return payload.get("responseObject", payload)
