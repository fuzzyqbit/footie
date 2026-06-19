# Phase 4 Research — Async Scraper Rewrite

**Phase:** 4 · **Requirements:** SCRAPE-01, SCRAPE-02, SCRAPE-03, SCRAPE-04
**Date:** 2026-06-19 · **Confidence:** HIGH on the httpx/asyncio API + integration shape; MEDIUM on the concurrency/rate *numbers* (tuning knobs, not correctness).
**Primary source:** `.planning/research/ASYNC-SCRAPING.md` (full design: AsyncFetcher code shape, verified httpx 0.28.1 signatures, ranked equivalence risks, sequencing). This distills it to the Phase 4 build + Validation Architecture.

## What earlier phases already did (don't redo)
- **Phase 2** made `db.upsert` batched/atomic and the read cache process-global. Refresh already wraps expand+enrich in `with repo.batch():` (`refresh.py:55`) → one flush per run. The async rewrite keeps that batch; concurrency is added to **fetch**, not to writes.
- **Phase 2 proved the single-writer contract** the async design must mirror: `images.py:230-268` fetches concurrently in a ThreadPoolExecutor but every `repo.upsert` runs on the one consuming thread (whole-file rewrite → concurrent writers clobber).
- The offline refresh benchmark (`tests/benchmarks/test_bench_refresh.py`) deliberately benches only the **write** cost (bulk upsert), excluding network — so it will NOT show the async win. Phase 4 must add a **simulated-latency** benchmark to prove concurrency (see 04-03).

## Verified facts (from ASYNC-SCRAPING.md live introspection — not training memory)
- Python **3.14.5**, httpx **0.28.1** in `.venv`. `asyncio.run`, `asyncio.to_thread`, `asyncio.Semaphore`, `asyncio.gather` all stable.
- `httpx.Limits(max_connections, max_keepalive_connections, keepalive_expiry)`, `httpx.Timeout(connect=, read=, write=, pool=)` confirmed.
- **`AsyncHTTPTransport(retries=N)` retries ONLY ConnectError/ConnectTimeout** — NOT 5xx/read errors. Current `fetch_html` (`web.py:13-26`) retries on **any** `httpx.HTTPError`. To stay output-equivalent on the error path we replicate "1 retry on any HTTPError" in our own wrapper; do NOT lean on transport `retries=`.
- **Hosts = 3** (`fut.gg`, `fcratings.com`, `futbin.com`) — grepped from all URL literals in `fc26/ingest/`.
- **No `pytest-asyncio` / `anyio` test plugin installed** (checked `pyproject.toml` dev deps: `pytest>=8, pytest-cov, pytest-benchmark, py-spy`). **Async tests & benches drive coroutines via `asyncio.run(...)` inside plain sync test functions** — no new dependency, no `@pytest.mark.asyncio`. This is a hard constraint on every test in 04-01/02/03.

## Phase 4 scope (all equivalence-gated by the Phase 1 golden + new fixtured diff)

### SCRAPE-01/02/03 mechanism — async fetch core (Plan 04-01)
New `fc26/ingest/web_async.py` (alongside `web.py`, which stays for the sync path / sbc / objectives):
- **`AsyncFetcher`** — context manager owning one shared `httpx.AsyncClient` (`Limits(max_connections=8, max_keepalive_connections=8, keepalive_expiry=30.0)`, `Timeout(connect=10, read=15, write=10, pool=5)`, `follow_redirects=True`, UA `footie-playbook/0.1 (personal squad tool)` identical to `web.py:9`). `concurrency` and `min_interval` are **constructor params** (defaults 4 / 1.0) — never hard-coded aggressive.
- **`asyncio.Semaphore(concurrency)`** — hard cap on simultaneous in-flight requests (SCRAPE-02 bounded concurrency).
- **`HostRateLimiter(min_interval)`** — per-host (`urlsplit(url).netloc`) min-interval gate + `random.uniform(0, min_interval)` jitter, serialized by a per-host `asyncio.Lock`. Reproduces the old global `sleep(1.0)` politeness **per host** so the 3 hosts throttle independently (SCRAPE-02 rate + jitter).
- **`fetch(url)`** — per-host wait → acquire semaphore → `client.get` → `raise_for_status` → on **any `httpx.HTTPError`**, retry once (modest `random.uniform(0,0.5)` backoff, strictly politer, only on retry) → on final failure raise `FetchError(f"could not fetch {url}: {last_error}")` **wording identical to `web.py:26`** (SCRAPE-03 retry parity).
- **Why both Semaphore AND HostRateLimiter:** semaphore caps *simultaneity*; limiter caps *rate*. A semaphore alone lets N requests fire the instant slots free (bursts → IP blocks). Need both.

### SCRAPE-03/04 — async ingest variants ALONGSIDE the sync ones (Plan 04-02)
Keep `enrich_cards` / `expand_cards` / `upgrade_card_images` / `refresh_data` **unchanged** (all existing tests stay green). ADD async siblings taking a `fetcher` (AsyncFetcher) instead of `fetch_html`/`sleep`:
- **`enrich_cards_async`** — the order-sensitive one. SERIAL pre-pass resolves every player URL **including lazy club discovery** (`club_urls`/`club_pages` built single-threaded — guards risk #3) → `asyncio.gather` the player-page fetches with **error isolation** (each task returns `(card, html|None, exc)`, never raises out — NOT a TaskGroup, which cancels siblings) → SERIAL upsert loop **in card order** that runs `parse_player_page` + `repo.upsert`, increments `attempts`/`failures`, applies the `ABORT_FAILURE_RATIO`/`ABORT_CHECK_AFTER` early-abort, and emits `on_progress` **only from this serial consumer** (guards risk #1, #4, #5). Returns the identical `EnrichResult` tuples.
- **`upgrade_card_images_async`** — gather detail-page fetches → serial upsert **in card order** (matches the deterministic `workers=1` output, NOT the `as_completed` threaded order). Preserves `ImagesResult` + abort counters.
- **`expand_cards_async`** — stays **SEQUENTIAL** (pagination is data-dependent: `while True` breaks on empty/short page; `_resolve` calls `find_by_id` on prior upserts → id-suffix depends on upsert order — risk #2 HIGH). Just routes each page fetch through the AsyncFetcher for connection reuse. Look-ahead prefetch explicitly deferred to v2 (correctness > the few list pages above min_ovr 84).
- **`refresh_data_async`** — `async with AsyncFetcher(...) as f:` wrap `with repo.batch():` → `await expand_cards_async(...)` then `await enrich_cards_async(...)`; manifest write unchanged. Same `RefreshResult`.

### SCRAPE-01/04 — wire + prove (Plan 04-03)
- **CLI** (`cli.py` `refresh`/`enrich`/`expand`/`images`, lines 184-311): wrap each in `asyncio.run(*_async(...))` inside the existing `with repo.batch():`. Typer commands are sync → no running loop → `asyncio.run` is clean. Output text **unchanged**.
- **FastAPI** (`app.py` `_refresh_loop`, `:97-101`): `await asyncio.to_thread(lambda: asyncio.run(refresh_data_async(...)))`. Worker thread has no loop → fresh loop, never nested in uvicorn's; keeps the whole scrape incl. upsert file I/O off the server loop, exactly as today. No `nest_asyncio`. `_META_CACHE.clear()` bust unchanged.
- **Flip defaults to async**; sync funcs remain (tests + sbc/objectives).
- **Simulated-latency benchmark** (`tests/benchmarks/test_bench_refresh.py` add-on): a stub async fetcher whose `fetch` does `await asyncio.sleep(~5ms)` over the fixture corpus; assert async refresh wall-clock is materially **below** the sequential sum-of-sleeps. Proves the concurrency win deterministically, no network.

## Output-equivalence risks (ranked — MUST guard; guarded by 04-02 fixtured diff + Phase 1 golden)
1. **Concurrent upsert corrupts data (CRITICAL)** → exactly one serial writer; gather does fetch+parse only. Mirrors `images.py` single-writer rule.
2. **`expand._resolve` id-suffix depends on upsert order (HIGH)** → keep `expand` sequential.
3. **enrich shared `club_urls`/`club_pages` cache (MED)** → resolve all URLs incl. club discovery serially *before* gather.
4. **progress/log line order (MED)** → emit `on_progress` only from the serial consumer, never a gathered task.
5. **`merge_cards` field precedence under reorder (MED)** → preserve card iteration order in the serial upsert.
6. **retry/error semantics drift (LOW/MED)** → 1 retry on ANY `httpx.HTTPError`; `FetchError` wording byte-identical.

## Politeness contract (must NOT regress)
Per-host ~1 req/s preserved via `HostRateLimiter`; `Semaphore` caps simultaneity; jitter preserved (`random.uniform(0,min_interval)`); shared client + keepalive = fewer handshakes (strictly politer); backoff only on the retry path. `concurrency`/`min_interval` are conservative params, raised only against the benchmark.

## Hard constraints
Byte-identical `data/players.json` + identical CLI/API text + identical result tuples + identical progress sequence (Phase 1 golden + new fixtured sync-vs-async diff are the gate). All existing tests green. No new infra. No on-disk format change. No new runtime dependency (drive async tests with `asyncio.run`). `sbc.py`/`objectives.py` stay on the sync path for v1 (distinct browser UA + raise `httpx.HTTPError` not `FetchError` — see `sbc.py:86-101`, `objectives.py:55-70`); do not route them through the fetcher now.

## Validation Architecture

> nyquist_validation `true` — section included.

### Test framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8 (+ pytest-benchmark from Phase 1). NO pytest-asyncio → coroutines driven via `asyncio.run()` in sync tests. |
| Quick run | `FORCE_COLOR= NO_COLOR=1 pytest -q` (must stay green; esp. test_enrich, test_expand, test_images, test_refresh, test_web) |
| Equivalence gate | `FORCE_COLOR= NO_COLOR=1 pytest -m golden --run-bench` (refresh_players bytes + readback) **plus** `tests/test_ingest_async.py` (fixtured sync-vs-async byte-identical diff) |
| Speed gate | `FORCE_COLOR= NO_COLOR=1 pytest -m benchmark --run-bench --benchmark-storage=.benchmarks --benchmark-compare=0003 --benchmark-compare-fail=mean:10%` then re-baseline `0004`; the new simulated-latency bench asserts async refresh ≪ sequential sum-of-sleeps |
| Env note | `FORCE_COLOR=3` is set in this shell → ALWAYS prefix `FORCE_COLOR= NO_COLOR=1` or 5 CLI tests show spurious ANSI failures |

### Phase requirements → test map
| Req | Behavior | Test type | Command | Exists? |
|-----|----------|-----------|---------|---------|
| SCRAPE-01 | Shared `AsyncClient` w/ connection reuse; CLI+API route through it | unit + integration | `pytest tests/test_web_async.py`; `pytest tests/test_cli.py tests/test_api.py` | ❌ W0 test_web_async + ✅ existing cli/api |
| SCRAPE-02 | Semaphore bound + per-host min-interval + jitter; politeness preserved | unit | `pytest tests/test_web_async.py -k "rate or semaphore or jitter"` | ❌ W0 test_web_async |
| SCRAPE-03 | One bad card/page doesn't abort batch; 1-retry-on-any-HTTPError; FetchError wording identical | unit + equivalence | `pytest tests/test_web_async.py -k retry`; `pytest tests/test_ingest_async.py -k "miss or error"` | ❌ W0 |
| SCRAPE-04 | Async wired to CLI (`asyncio.run`) + API (`to_thread(asyncio.run)`); single serial writer; expand order preserved; byte-identical | golden + equivalence + integration | `pytest -m golden --run-bench`; `pytest tests/test_ingest_async.py`; `pytest tests/test_cli.py tests/test_api.py` | ❌ W0 test_ingest_async + ✅ golden/cli/api |
| (all) | existing tests green; golden byte-identical; bench no regression vs 0003 | regression | `pytest -q` + golden + benchmark gate | ✅ existing + Phase 1 |

### Wave 0
- `tests/test_web_async.py` — AsyncFetcher unit tests (driven by `asyncio.run`): per-host min-interval enforced; jitter present; semaphore cap never exceeded (track concurrent in-flight peak); 1 retry on any HTTPError (a 500 retried once then `FetchError`); `FetchError` message byte-identical to `web.py` wording; UA + limits set on the client.
- `tests/test_ingest_async.py` — fixtured **sync-vs-async equivalence**: run `enrich_cards`/`expand_cards`/`upgrade_card_images`/`refresh_data` and their `_async` siblings over the SAME fixtures + a tmp corpus repo; assert (a) result tuples EQUAL, (b) `players.json` bytes IDENTICAL, (c) `on_progress` sequence EQUAL. This is the byte-identical gate for the rewrite. Reuse `tests/fixtures/*.html` + the monkeypatch-parse seam + a new `offline_fetch_async` helper (async analog of `corpus.offline_fetch`).
- No new golden fixture needed for the write path — Phase 1 `refresh_players.json`/`refresh_readback.json` + the new fixtured diff cover it. The simulated-latency bench (04-03) is a `@pytest.mark.benchmark` add to `test_bench_refresh.py`.

## Security domain
No new endpoints/auth/input/crypto — outbound scraper only. The relevant control is **politeness (rate-limit)**, which must not regress: per-host min-interval + bounded concurrency + jitter + connection reuse are all strictly ≤ today's load per host. Concurrency adds shared-state hazards (shared `club_*` cache, single-writer) — mitigated by resolving URLs before gather and serial upsert. `sbc.py`/`objectives.py` keep their distinct browser UA + `httpx.HTTPError` type (left on sync path). ASVS: none directly applicable.

## Sources
- `.planning/research/ASYNC-SCRAPING.md` (primary — verified httpx 0.28.1 signatures, AsyncFetcher/HostRateLimiter code, ranked equivalence risks, CLI/API integration, sequencing).
- Code (read directly): `fc26/ingest/{web,enrich,expand,images,refresh}.py`, `fc26/cli.py` (refresh/enrich/expand/images cmds), `fc26/api/app.py` (`_refresh_loop`, `_META_CACHE`).
- Test seams: `tests/{test_enrich,test_expand,test_refresh}.py` (monkeypatch-parse + injected `fetch_html`), `tests/benchmarks/{corpus,conftest,test_bench_refresh,test_golden_refresh}.py`, `tests/conftest.py` (`--run-bench`), `pyproject.toml` (markers + dev deps — no pytest-asyncio).
- Phase 1 golden + `.benchmarks/0003` (Phase 3 baseline).
