"""Async HTTP fetch core for ingest crawlers.

Replaces the per-call ``httpx.get`` in ``web.py`` with a single long-lived
``AsyncClient`` (connection reuse) bounded by two independent controls:

* an ``asyncio.Semaphore`` caps *simultaneity* (how many requests are in flight
  at once), and
* a per-host :class:`HostRateLimiter` caps *rate* (the min interval between
  request starts to one host, with jitter).

You need both: a semaphore alone lets N requests fire the instant slots free up
(a burst), which is what gets IPs blocked. The limiter reproduces the politeness
of the old sequential ``sleep(1.0)`` but measured *per host*, so fut.gg /
fcratings / futbin throttle independently and can overlap.

The retry path deliberately mirrors ``web.py``: one retry on *any*
``httpx.HTTPError`` and the identical ``FetchError`` wording. We do NOT use
``AsyncHTTPTransport(retries=)`` because that only retries ConnectError /
ConnectTimeout, not 5xx / read errors — which would change the error behaviour.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from urllib.parse import urlsplit

import httpx

from ..errors import FetchError

USER_AGENT = "footie-playbook/0.1 (personal squad tool)"

# Cap total + keepalive so connections are REUSED per host (fewer TCP/TLS
# handshakes than the old new-connection-per-call design = strictly politer).
_LIMITS = httpx.Limits(max_connections=8, max_keepalive_connections=8, keepalive_expiry=30.0)
# Granular timeouts: keep read generous (matches the old flat 15s), add a pool
# timeout so a saturated pool surfaces fast instead of hanging.
_TIMEOUT = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)


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
    """Shared ``AsyncClient`` + bounded, polite concurrency. Async ``fetch_html``.

    ``concurrency`` and ``min_interval`` are conservative parameters, not
    hard-coded aggressive values — raise them only against the benchmark.
    """

    def __init__(self, *, concurrency: int = 4, min_interval: float = 1.0,
                 retries: int = 1) -> None:
        self._sem = asyncio.Semaphore(concurrency)      # hard cap on in-flight
        self._rl = HostRateLimiter(min_interval)
        self._retries = retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncFetcher":
        self._client = httpx.AsyncClient(
            limits=_LIMITS, timeout=_TIMEOUT, follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def fetch(self, url: str) -> str:
        """GET a page (1 retry on any HTTPError), or raise FetchError."""
        host = urlsplit(url).netloc
        last: Exception | None = None
        # Match web.py: 1 retry on ANY httpx.HTTPError (NOT transport retries=,
        # which only covers ConnectError) -> output-equivalent error behaviour.
        for _ in range(self._retries + 1):
            await self._rl.wait(host)            # politeness gate (per host), no slot held
            async with self._sem:                # concurrency cap (global)
                try:
                    resp = await self._client.get(url)
                    resp.raise_for_status()
                    return resp.text
                except httpx.HTTPError as exc:
                    last = exc
                    # modest backoff + jitter, ONLY on the retry path: strictly
                    # politer than the old immediate retry, still <= old total.
                    await asyncio.sleep(random.uniform(0.0, 0.5))
        raise FetchError(f"could not fetch {url}: {last}")
