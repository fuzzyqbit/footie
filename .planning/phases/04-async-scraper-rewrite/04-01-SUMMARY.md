# 04-01 SUMMARY — Async fetch core

**Status:** ✅ complete · **Wave:** 1 · **Requirements:** SCRAPE-01, SCRAPE-02, SCRAPE-03 (fetch-level)

## What was built
- `fc26/ingest/web_async.py` (new):
  - `HostRateLimiter(min_interval)` — per-host (netloc) min-interval gate + `random.uniform(0, min_interval)` jitter, serialized by a per-host `asyncio.Lock`.
  - `AsyncFetcher(*, concurrency=4, min_interval=1.0, retries=1)` — context manager owning one shared `httpx.AsyncClient` (`Limits(max_connections=8, max_keepalive_connections=8, keepalive_expiry=30)`, `Timeout(connect=10, read=15, write=10, pool=5)`, `follow_redirects=True`, UA identical to `web.py`). `fetch(url)`: per-host wait (outside the semaphore so the wait holds no slot) → `asyncio.Semaphore(concurrency)` → `client.get` → `raise_for_status` → **1 retry on any `httpx.HTTPError`** (modest `random.uniform(0,0.5)` backoff only on retry) → `FetchError(f"could not fetch {url}: {last}")` (wording identical to `web.py:26`).
- `tests/test_web_async.py` (new, 7 tests, all green) — driven by `asyncio.run` (no pytest-asyncio): per-host interval floor; cross-host overlap; jitter band on next-allowed; semaphore peak == cap (never exceeded); retry on 500-then-200 (proves 5xx is retried, which transport `retries=` would not); persistent 500 → `FetchError` with identical wording; client carries the UA.

## Decisions / deviations
- No `AsyncHTTPTransport(retries=)` — it only covers ConnectError/ConnectTimeout; manual loop replicates the broader "1 retry on any HTTPError" for output-equivalent error behavior.
- Semaphore + HostRateLimiter are independent (simultaneity cap vs rate cap) per the research — both required.
- No new runtime dependency. Tests use `httpx.MockTransport` + a stub client; zero network.

## Verification
- `FORCE_COLOR= NO_COLOR=1 pytest tests/test_web_async.py -q` → 7 passed.
- Full suite still green (no import/collection breakage).
