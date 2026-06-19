# Roadmap: footie — Performance & Speed Milestone

## Overview

This is a brownfield performance milestone: make footie noticeably faster across scraping, backend, and web load while producing **byte-for-byte identical output** — same `data/players.json`, same API responses, same CLI text, all existing tests green. The journey starts by building the missing measurement instrument and golden-output safety net (no benchmark exists today), then attacks the single root-cause bottleneck — the whole-file JSON re-read/rewrite in `fc26/db.py` — with an in-process cache and batched writes. From there it works outward through the dependency chain: API responsiveness (off-event-loop compute, memoization, cached `/api/meta`), an async scraper rewrite (concurrent fetch / serial writer, politeness preserved), and finally frontend code-splitting plus CLI startup. Every phase is gated by the Phase 1 harness: a speed win only counts if a benchmarked path measurably improves AND the golden-equivalence check still passes. No new infrastructure (no Redis/Memcached/RabbitMQ), no on-disk format change.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Benchmark & Equivalence Harness** ✓ - Measurement instrument + golden-output safety net with committed baselines; lands first, nothing optimized ships without it
- [x] **Phase 2: Data-Layer Cache & Batched Writes** ✓ - In-process id-indexed read cache over `db.py` + batched/atomic+durable writes that kill the O(n²) refresh rewrite
- [ ] **Phase 3: API Responsiveness** - Off-event-loop handlers, memoized pure helpers + per-card chem facts, cached `/api/meta`, hoisted hot loops
- [ ] **Phase 4: Async Scraper Rewrite** - Shared `httpx.AsyncClient`, bounded concurrency + per-host politeness, error isolation, CLI+API integration with single serial writer
- [ ] **Phase 5: Frontend Load & CLI Startup** - Route code-splitting, lazy WASM dep + dead-dep removal, React Query tuning, CLI deferred imports

## Phase Details

### Phase 1: Benchmark & Equivalence Harness
**Goal**: A reusable harness exists that both measures the speed of every hot path against committed baselines AND proves outputs are unchanged after any optimization — the prerequisite that gates every later phase.
**Depends on**: Nothing (first phase)
**Requirements**: BENCH-01, BENCH-02, BENCH-03, BENCH-04
**Success Criteria** (what must be TRUE):
  1. Running the benchmark suite on `ro` HEAD captures and commits baselines for refresh (mocked HTTP + stubbed sleep), `/api/cards`, `/api/build`, `/api/upgrade`, `/api/meta`, and `db.py` read/write — gated behind a `benchmark` marker so the default `pytest` run stays fast.
  2. A regression gate (`--benchmark-compare-fail mean:10%`) flags any benchmarked path that slows past the threshold versus the committed baseline.
  3. A golden-output/equivalence check captures current outputs (refresh-produced `players.json` bytes + result tuples + progress-line sequence; a build/upgrade matrix over formations × objectives × budgets; key API responses; CLI text) and re-asserts structural equality — providing the gate that enforces zero behavior change.
  4. Profiling entrypoints (cProfile and py-spy) are documented for the refresh and build/upgrade hot paths.
  5. All existing tests (pytest offline, vitest, e2e) stay green; the harness adds measurement only and changes no observable behavior.
**Plans**: TBD

### Phase 2: Data-Layer Cache & Batched Writes
**Goal**: The card pool is read from an in-process, id-indexed cache instead of re-parsing the 4.4 MB `data/players.json` on every call, and refresh writes once atomically instead of rewriting the whole file per card — the biggest, lowest-risk win, unblocking both API and refresh.
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. The `db.py` read benchmark shows `find_all()`/`find_by_id` measurably faster than the Phase 1 baseline (full re-parse collapses to a cached lookup; `find_by_id` becomes O(1)), with the process-global cache surviving the ~12 per-request `CardRepository(db_path)` constructions.
  2. The refresh benchmark shows a materially lower wall-clock and the `_atomic_write` call count drops from ~2,400 to 1 per run (batched, temp→rename + fsync of file and parent dir).
  3. The cache invalidates correctly on write/refresh and across the CLI-writes-while-server-runs case (mtime+size re-stat), verified by a dedicated test that externally rewrites the file and asserts the next read reloads.
  4. The golden-equivalence check passes: `data/players.json` stays byte-identical (id-sorted on save preserved), `find_all` returns an immutable snapshot so upsert-during-iteration behavior is unchanged, and the default non-batched upsert path still flushes every write.
  5. All existing tests stay green.
**Plans**: TBD

### Phase 3: API Responsiveness
**Goal**: The API stays responsive under concurrent load and per-request cost drops, by moving blocking compute off the event loop, memoizing pure helpers and per-card chemistry facts, and caching the static `/api/meta` — all with byte-identical responses.
**Depends on**: Phase 2
**Requirements**: API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. Blocking/CPU handlers no longer run on the event loop (sync `def` GETs auto-offloaded; POST `/api/build`/`/api/upgrade`/`/api/chem`/`/api/boost` via `run_in_threadpool`), so concurrent requests don't serialize — demonstrable on the API benchmark under concurrency.
  2. The `/api/build` and `/api/upgrade` benchmarks improve versus the Phase 2 baseline via memoized `slugify`/`canonical_*`, precomputed per-card chem facts, and invariant work hoisted out of the inner loops.
  3. `/api/meta` is cached keyed on pool mtime and busted on refresh, with the benchmark faster and the response byte-identical — including the version-filter quirk preserved (`versions` unfiltered, `leagues`/`nations`/`clubs` filter falsy).
  4. The golden-equivalence check passes for all touched endpoints, and `_same_player` prefix semantics + candidate order tie-breaks are preserved.
  5. All existing tests stay green.
**Plans**: TBD

### Phase 4: Async Scraper Rewrite
**Goal**: Ingest fetches concurrently over a shared async client with bounded, polite concurrency and error isolation, while writing through a single serial writer so scraped output stays equivalent — turning serial-sleep-dominated refresh into a parallel pipeline.
**Depends on**: Phase 3
**Requirements**: SCRAPE-01, SCRAPE-02, SCRAPE-03, SCRAPE-04
**Success Criteria** (what must be TRUE):
  1. Ingest fetches over a shared `httpx.AsyncClient` with connection reuse, and the offline refresh benchmark (mocked HTTP) shows a materially lower wall-clock than the Phase 2 baseline.
  2. Concurrency is bounded by a semaphore with per-host rate limiting + jitter, demonstrably preserving the per-host ~1 req/s politeness to fut.gg/fcratings/futbin (conservative defaults, tuned only against the harness).
  3. A single failing card/page does not abort the batch — error isolation with retry/backoff matching the current 1-retry semantics.
  4. The async pipeline integrates with the sync CLI (`asyncio.run`) and the FastAPI background loop (no nested loops), using a single serial writer in card order and preserved `expand` id-suffix ordering — so the golden-equivalence check passes (byte-identical `players.json`, identical result tuples and progress sequence) before the async path becomes default.
  5. All existing tests stay green.
**Plans**: TBD

### Phase 5: Frontend Load & CLI Startup
**Goal**: The web app's initial download shrinks and navigation stops refetching static data, and the CLI starts fast for `--help`/simple commands — the user-facing load wins, parallelizable once the harness is green.
**Depends on**: Phase 4
**Requirements**: WEB-01, WEB-02, WEB-03, CLI-01
**Success Criteria** (what must be TRUE):
  1. Routes are code-split with `React.lazy` + `Suspense` (one chunk per page) and a build-size diff shows the initial JS bundle materially smaller than today's ~298 KB.
  2. Heavy/WASM deps load only on the page that needs them (GeneratorPage's `@imgly` chunk leaves the initial download) and the unused `html-to-image` dependency is removed.
  3. React Query is configured with sensible `staleTime`/`gcTime`/`refetchOnWindowFocus:false` so navigation no longer refetches static `/api/meta` + `/api/cards` data.
  4. The CLI startup benchmark (`python -X importtime -m fc26 --help`) is measurably faster via deferred heavy imports, while command behavior and output are unchanged.
  5. All existing tests stay green (vitest + e2e specs wait on page content, not spinner absence) and the golden-equivalence check passes — no observable behavior change.
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Benchmark & Equivalence Harness | 0/TBD | Not started | - |
| 2. Data-Layer Cache & Batched Writes | 0/TBD | Not started | - |
| 3. API Responsiveness | 0/TBD | Not started | - |
| 4. Async Scraper Rewrite | 0/TBD | Not started | - |
| 5. Frontend Load & CLI Startup | 0/TBD | Not started | - |
