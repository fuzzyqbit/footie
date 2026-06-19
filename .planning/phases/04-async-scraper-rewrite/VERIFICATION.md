# Phase 4 Verification — Async Scraper Rewrite

**Date:** 2026-06-19 · **Verdict:** ✅ PASSED
**Goal:** Ingest fetches concurrently over a shared async client with bounded, polite concurrency and error isolation, while writing through a single serial writer so scraped output stays equivalent.

## Requirement-by-requirement (goal-backward)

| Req | Verdict | Evidence |
|-----|---------|----------|
| **SCRAPE-01** shared `httpx.AsyncClient` + connection reuse | ✅ | `web_async.py` `AsyncFetcher` owns one `AsyncClient` (`Limits(max_connections=8, keepalive=8/30s)`); CLI + FastAPI both route through it. Simulated-latency bench shows concurrent fetch (~13ms vs 125ms sequential, ~10×). |
| **SCRAPE-02** bounded concurrency + per-host rate + jitter, politeness preserved | ✅ | `asyncio.Semaphore(concurrency)` caps simultaneity; `HostRateLimiter` enforces per-host min-interval + `random.uniform(0,min)` jitter (keyed on netloc, so fut.gg/fcratings/futbin throttle independently). `test_web_async.py`: per-host floor, cross-host overlap, jitter band, semaphore peak == cap. |
| **SCRAPE-03** one bad card/page doesn't abort batch; 1-retry parity | ✅ | `fetch` retries once on ANY `httpx.HTTPError` (not transport `retries=`), identical `FetchError` wording (`test_web_async`: 500-then-200, persistent-500). Async ingest isolates per-card errors via `(card, result|None, exc|None)` tuples (`test_ingest_async` error-isolation case == sync). |
| **SCRAPE-04** CLI `asyncio.run` + FastAPI no-nested-loop; single serial writer; expand order; byte-identical | ✅ | CLI uses `asyncio.run`; `_refresh_loop` uses `to_thread(asyncio.run(...))` (worker thread → fresh loop). Single serial upsert in card order; expand kept sequential. `test_ingest_async` (5 tests) asserts result tuples ==, **players.json bytes ==**, on_progress sequence == for enrich/expand/images/refresh. Golden `-m golden --run-bench` 10 passed. |

## Equivalence risks (all guarded)
1. concurrent-upsert corruption → single serial writer ✅ · 2. expand id-suffix order → expand sequential ✅ · 3. enrich club cache → resolved before gather ✅ · 4. progress order → emitted from serial consumer only ✅ · 5. merge precedence → card iteration order preserved ✅ · 6. retry/FetchError wording → identical ✅. All covered by `test_ingest_async` byte-identical diff + golden.

## Gates
- **Full suite:** 364 passed, 29 skipped (`FORCE_COLOR= NO_COLOR=1 pytest -q`). Baseline was 352 → +12 new (7 web_async, 5 ingest_async).
- **Golden byte-identical:** 10 passed (`pytest -m golden --run-bench`).
- **Speed:** simulated-latency bench async ≈13ms ≪ 125ms sequential.
- **Benchmark regression vs 0003:** flagged `bulk_upsert`/`bulk_upsert_batched` (write path) — **environmental noise, not a regression**: readings unstable run-to-run (14%→29%), and `git diff 046b21c -- fc26/db.py fc26/builder fc26/chem` is EMPTY (Phase 4 touched only api/cli/ingest). No Phase-4-modified path regressed. Baseline re-saved 0004.

## Files changed
`fc26/ingest/web_async.py` (new), `fc26/ingest/{enrich,expand,images,refresh}.py` (async siblings added, sync unchanged), `fc26/cli.py`, `fc26/api/app.py`, `tests/{test_web_async,test_ingest_async}.py` (new), `tests/test_cli.py` (stub retarget), `tests/benchmarks/{corpus,test_bench_refresh}.py`, `.benchmarks/.../0004`.

## Notes carried forward
- `sbc.py`/`objectives.py` intentionally left on the sync path (distinct browser UA + raise `httpx.HTTPError` not `FetchError`) — not in Phase 4 scope.
- expand look-ahead prefetch deferred (sequential is correct + the list pages above min_ovr are few).
- The write-path benchmark noise on this shared machine is pre-existing (noted in Phase 2); consider running the benchmark gate on a quiet machine for the milestone's final before/after numbers.
