"""Async HTTP fetch core for ingest crawlers.

Uses ``curl_cffi`` with browser impersonation (Chrome TLS/JA3 + HTTP2
fingerprint) so requests get past Cloudflare's passive bot detection — a plain
``httpx``/``requests`` client is fingerprinted and 403'd by futbin. A single
long-lived ``AsyncSession`` (connection reuse) is bounded by two independent
controls:

* an ``asyncio.Semaphore`` caps *simultaneity* (how many requests are in flight
  at once), and
* a per-host :class:`HostRateLimiter` caps *rate* (the min interval between
  request starts to one host, with jitter).

You need both: a semaphore alone lets N requests fire the instant slots free up
(a burst), which is what gets IPs blocked. The limiter reproduces the politeness
of the old sequential ``sleep(1.0)`` but measured *per host*, so fut.gg /
fcratings / futbin throttle independently and can overlap.

The retry path mirrors ``web.py``: one retry on any request error and the
identical ``FetchError`` wording, so the error behaviour stays output-equivalent.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from urllib.parse import urlsplit

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from ..errors import FetchError

# curl_cffi's legacy base error isn't always a subclass of RequestException;
# catch both so "1 retry on any request failure" holds.
try:  # pragma: no cover - import shim across curl_cffi versions
    from curl_cffi.requests.errors import RequestsError
    _FETCH_ERRORS: tuple[type[BaseException], ...] = (RequestException, RequestsError)
except Exception:  # pragma: no cover
    _FETCH_ERRORS = (RequestException,)

USER_AGENT = "footie-playbook/0.1 (personal squad tool)"

# Impersonate a real Chrome so Cloudflare's TLS/HTTP2 fingerprint check passes.
# (Overriding the User-Agent would break the fingerprint, so we let impersonate
# set the matching browser headers.)
IMPERSONATE = "chrome"
# Flat request timeout (seconds); curl_cffi takes a number or (connect, read).
_TIMEOUT_SECONDS = 20.0


class HostRateLimiter:
    """Per-host minimum interval between request *starts* (token bucket of size 1).

    Reproduces the politeness of the old sequential ``sleep(1.0)`` but keyed per
    host so unrelated hosts no longer block each other. The per-host lock
    serialises the gate so two coroutines targeting the same host can't both
    pass instantly.
    """

    def __init__(self, min_interval: float) -> None:
        self._min = min_interval
        self._next: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def wait(self, host: str) -> None:
        async with self._locks[host]:
            delay = self._next[host] - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            # jitter (0..min) preserves the old jittered_sleep anti-metronome
            # property so request timing doesn't look like a fixed bot cadence.
            self._next[host] = time.monotonic() + self._min + random.uniform(0, self._min)


class AsyncFetcher:
    """Shared impersonating ``AsyncSession`` + bounded, polite concurrency.

    ``concurrency`` and ``min_interval`` are conservative parameters, not
    hard-coded aggressive values — raise them only against the benchmark.
    """

    def __init__(self, *, concurrency: int = 4, min_interval: float = 1.0,
                 retries: int = 1) -> None:
        self._sem = asyncio.Semaphore(concurrency)      # hard cap on in-flight
        self._rl = HostRateLimiter(min_interval)
        self._retries = retries
        self._concurrency = concurrency
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "AsyncFetcher":
        self._session = AsyncSession(
            impersonate=IMPERSONATE,
            timeout=_TIMEOUT_SECONDS,
            max_clients=max(self._concurrency, 1),
            allow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session is not None:
            await self._session.close()

    async def fetch(self, url: str) -> str:
        """GET a page (1 retry on any request error), or raise FetchError."""
        host = urlsplit(url).netloc
        last: Exception | None = None
        for _ in range(self._retries + 1):
            await self._rl.wait(host)            # politeness gate (per host), no slot held
            async with self._sem:                # concurrency cap (global)
                try:
                    resp = await self._session.get(url)
                    resp.raise_for_status()
                    return resp.text
                except _FETCH_ERRORS as exc:
                    last = exc
                    # modest backoff + jitter, ONLY on the retry path: strictly
                    # politer than the old immediate retry.
                    await asyncio.sleep(random.uniform(0.0, 0.5))
        raise FetchError(f"could not fetch {url}: {last}")
