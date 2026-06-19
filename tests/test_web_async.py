"""Unit tests for the async fetch core (fc26/ingest/web_async.py).

No pytest-asyncio is installed, so every test drives coroutines with
``asyncio.run(...)`` from a plain sync function. Network is never touched:
rate/semaphore tests use a stub client; retry/UA tests use httpx.MockTransport
(real httpx Response objects so ``raise_for_status`` behaves correctly).
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from fc26.errors import FetchError
from fc26.ingest.web_async import USER_AGENT, AsyncFetcher, HostRateLimiter


class _StubClient:
    """Stands in for httpx.AsyncClient: only ``get`` + ``aclose`` are used."""

    def __init__(self, handler):
        self._handler = handler
        self.headers = {"user-agent": USER_AGENT}

    async def get(self, url):
        return await self._handler(url)

    async def aclose(self):
        pass


class _Resp:
    """Minimal response: ``text`` + ``raise_for_status`` no-op (success path)."""

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_per_host_min_interval_enforced():
    """Two requests to the SAME host: the second waits >= min_interval."""
    f = AsyncFetcher(concurrency=10, min_interval=0.05)

    async def _handler(url):
        return _Resp("ok")

    f._client = _StubClient(_handler)

    async def _run():
        t0 = time.monotonic()
        await f.fetch("https://www.fut.gg/a")
        await f.fetch("https://www.fut.gg/b")   # same host -> gated
        return time.monotonic() - t0

    elapsed = asyncio.run(_run())
    assert elapsed >= 0.05


def test_cross_host_requests_do_not_serialize():
    """A request to host A then host B is NOT gated by A's interval."""
    f = AsyncFetcher(concurrency=10, min_interval=0.3)

    async def _handler(url):
        return _Resp("ok")

    f._client = _StubClient(_handler)

    async def _run():
        t0 = time.monotonic()
        await f.fetch("https://www.fut.gg/a")
        await f.fetch("https://www.fcratings.com/a")   # different host -> no wait
        return time.monotonic() - t0

    elapsed = asyncio.run(_run())
    assert elapsed < 0.3


def test_jitter_band_on_next_allowed():
    """After one wait, the host's next-allowed is in [now+min, now+2*min)."""
    rl = HostRateLimiter(0.1)
    now = time.monotonic()
    asyncio.run(rl.wait("h"))
    nxt = rl._next["h"]
    assert now + 0.1 <= nxt <= now + 0.2 + 0.05   # +slack for scheduling


def test_semaphore_caps_in_flight():
    """With concurrency=2, no more than 2 requests are ever in flight at once."""
    f = AsyncFetcher(concurrency=2, min_interval=0.0)
    state = {"in_flight": 0, "peak": 0}

    async def _handler(url):
        state["in_flight"] += 1
        state["peak"] = max(state["peak"], state["in_flight"])
        await asyncio.sleep(0.02)
        state["in_flight"] -= 1
        return _Resp("ok")

    f._client = _StubClient(_handler)

    async def _run():
        await asyncio.gather(*(f.fetch(f"https://www.fut.gg/{i}") for i in range(5)))

    asyncio.run(_run())
    assert state["peak"] == 2          # exactly the cap was reached, never exceeded


def test_retry_once_on_any_httperror_then_succeeds():
    """A 500 then a 200: fetch retries once and returns the 200 body.

    Proves the retry covers 5xx (which transport retries= would NOT).
    """
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, text="recovered")

    f = AsyncFetcher(concurrency=4, min_interval=0.0)

    async def _run():
        f._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await f.fetch("https://www.futbin.com/x")
        finally:
            await f._client.aclose()

    body = asyncio.run(_run())
    assert body == "recovered"
    assert calls["n"] == 2             # one retry


def test_always_failing_raises_fetcherror_with_identical_wording():
    """Persistent 500 -> FetchError with the exact web.py wording."""
    def handler(request):
        return httpx.Response(500, text="boom")

    url = "https://www.futbin.com/down"
    f = AsyncFetcher(concurrency=4, min_interval=0.0)

    async def _run():
        f._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await f.fetch(url)
        finally:
            await f._client.aclose()

    with pytest.raises(FetchError) as ei:
        asyncio.run(_run())
    msg = str(ei.value)
    assert msg.startswith("could not fetch ")
    assert url in msg


def test_client_built_with_user_agent():
    """__aenter__ builds a client carrying the honest UA."""
    async def _run():
        async with AsyncFetcher() as f:
            return f._client.headers["user-agent"]

    assert asyncio.run(_run()) == USER_AGENT
