"""Unit tests for the async fetch core (fc26/ingest/web_async.py).

The fetcher uses a curl_cffi AsyncSession under the hood, but these tests are
transport-agnostic: they swap in a stub session (with `async def get`) so no
network is touched. No pytest-asyncio — coroutines run via asyncio.run().
"""

from __future__ import annotations

import asyncio
import time

import pytest
from curl_cffi.requests.exceptions import HTTPError

from fc26.errors import FetchError
from fc26.ingest.web_async import IMPERSONATE, AsyncFetcher, HostRateLimiter


class _Resp:
    """Stub response: text + raise_for_status (raises `error` if given)."""

    def __init__(self, text="ok", error: Exception | None = None):
        self.text = text
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error


class _StubSession:
    """Stands in for curl_cffi AsyncSession: only `get` + `close` are used."""

    def __init__(self, handler):
        self._handler = handler

    async def get(self, url):
        return await self._handler(url)

    async def close(self):
        pass


def test_per_host_min_interval_enforced():
    f = AsyncFetcher(concurrency=10, min_interval=0.05)

    async def _handler(url):
        return _Resp("ok")

    f._session = _StubSession(_handler)

    async def _run():
        t0 = time.monotonic()
        await f.fetch("https://www.fut.gg/a")
        await f.fetch("https://www.fut.gg/b")   # same host -> gated
        return time.monotonic() - t0

    assert asyncio.run(_run()) >= 0.05


def test_cross_host_requests_do_not_serialize():
    f = AsyncFetcher(concurrency=10, min_interval=0.3)

    async def _handler(url):
        return _Resp("ok")

    f._session = _StubSession(_handler)

    async def _run():
        t0 = time.monotonic()
        await f.fetch("https://www.fut.gg/a")
        await f.fetch("https://www.fcratings.com/a")   # different host -> no wait
        return time.monotonic() - t0

    assert asyncio.run(_run()) < 0.3


def test_jitter_band_on_next_allowed():
    rl = HostRateLimiter(0.1)
    now = time.monotonic()
    asyncio.run(rl.wait("h"))
    assert now + 0.1 <= rl._next["h"] <= now + 0.2 + 0.05


def test_semaphore_caps_in_flight():
    f = AsyncFetcher(concurrency=2, min_interval=0.0)
    state = {"in_flight": 0, "peak": 0}

    async def _handler(url):
        state["in_flight"] += 1
        state["peak"] = max(state["peak"], state["in_flight"])
        await asyncio.sleep(0.02)
        state["in_flight"] -= 1
        return _Resp("ok")

    f._session = _StubSession(_handler)

    async def _run():
        await asyncio.gather(*(f.fetch(f"https://www.fut.gg/{i}") for i in range(5)))

    asyncio.run(_run())
    assert state["peak"] == 2


def test_retry_once_on_error_then_succeeds():
    calls = {"n": 0}

    async def _handler(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp("boom", error=HTTPError("500 Server Error"))
        return _Resp("recovered")

    f = AsyncFetcher(concurrency=4, min_interval=0.0)
    f._session = _StubSession(_handler)

    assert asyncio.run(f.fetch("https://www.futbin.com/x")) == "recovered"
    assert calls["n"] == 2  # one retry


def test_always_failing_raises_fetcherror_with_identical_wording():
    url = "https://www.futbin.com/down"

    async def _handler(u):
        return _Resp("boom", error=HTTPError("500 Server Error"))

    f = AsyncFetcher(concurrency=4, min_interval=0.0)
    f._session = _StubSession(_handler)

    with pytest.raises(FetchError) as ei:
        asyncio.run(f.fetch(url))
    msg = str(ei.value)
    assert msg.startswith("could not fetch ")
    assert url in msg


def test_session_built_with_chrome_impersonation():
    assert IMPERSONATE == "chrome"

    async def _run():
        async with AsyncFetcher() as f:
            return f._session is not None

    assert asyncio.run(_run())
