# Requirements: footie — Performance & Speed Milestone

**Defined:** 2026-06-17
**Core Value:** footie runs noticeably faster (scraping, backend, web) while producing byte-for-byte identical output.

## User Stories

- As the **operator**, I want `fc26 refresh` to finish much faster so updating the card pool isn't a long wait.
- As a **web user**, I want pages (card lists, squad build/upgrade) to respond quickly and the app to load fast on first visit.
- As the **maintainer**, I want measurable benchmarks + a golden-output check so I can prove speedups and be sure behavior never changed.

## v1 Requirements

Each requirement is a speed improvement that must NOT change observable output. Maps to roadmap phases.

### Benchmarking & Safety (BENCH) — prerequisite

- [ ] **BENCH-01**: A reusable benchmark harness measures refresh, key API endpoints (`/api/cards`, `/api/build`, `/api/upgrade`, `/api/meta`) and db read/write, with committed baselines
- [ ] **BENCH-02**: A regression gate flags when a benchmarked path slows beyond a set threshold (e.g. mean +10%)
- [ ] **BENCH-03**: A golden-output/equivalence check captures current outputs (`data/players.json` shape, API responses, CLI text) and asserts they are unchanged after each optimization
- [ ] **BENCH-04**: Profiling entrypoints (cProfile / py-spy) are documented for the refresh and build/upgrade hot paths

### Data Layer (DATA)

- [ ] **DATA-01**: The card pool is loaded once into an in-process, id-indexed cache; reads no longer re-parse the full `data/players.json` on each call
- [ ] **DATA-02**: The cache invalidates correctly on write/refresh and across the CLI-writes-while-server-runs case (mtime+size tracking)
- [ ] **DATA-03**: Refresh writes are batched + atomic (one write per run, temp→rename + fsync), eliminating the O(n²) per-card full-file rewrite
- [ ] **DATA-04**: `find_all` returns an immutable snapshot so upsert-during-iteration behavior is preserved

### API Responsiveness (API)

- [ ] **API-01**: Blocking/CPU handlers no longer block the event loop, so concurrent requests don't serialize
- [ ] **API-02**: Pure helpers (`slugify`/`canonical_*`) and per-card chemistry facts are memoized/precomputed; build/upgrade hot loops hoist invariant work out of the inner loop
- [ ] **API-03**: `/api/meta` is cached and invalidated on refresh, with byte-identical output preserved

### Scrapers / Ingest (SCRAPE)

- [ ] **SCRAPE-01**: Ingest fetches over a shared `httpx.AsyncClient` with connection reuse
- [ ] **SCRAPE-02**: Concurrency is bounded (semaphore) with per-host rate limiting + jitter, preserving politeness to fut.gg/fcratings/futbin
- [ ] **SCRAPE-03**: A single failing card/page does not abort the batch (error isolation + retry/backoff matching current 1-retry semantics)
- [ ] **SCRAPE-04**: The async pipeline integrates with the sync CLI (`asyncio.run`) and the FastAPI background loop without nested loops, with a single serial writer and preserved expand ordering so scraped output stays equivalent

### Web App Load (WEB)

- [ ] **WEB-01**: Routes are code-split (`React.lazy` + `Suspense`); the initial JS bundle shrinks materially
- [ ] **WEB-02**: Heavy/WASM deps load only on the page that needs them; the unused `html-to-image` dependency is removed
- [ ] **WEB-03**: React Query is configured with sensible `staleTime`/`gcTime`/`refetchOnWindowFocus` so navigation doesn't refetch static data

### CLI Startup (CLI)

- [ ] **CLI-01**: CLI startup defers heavy imports so `--help` and simple commands run fast

## Acceptance Criteria

- Every existing test (pytest offline, vitest, Playwright e2e) stays green, unedited where it encodes the behavior contract.
- The golden-output/equivalence check (BENCH-03) passes after every optimization.
- Benchmarked paths (BENCH-01) show measurable improvement vs committed baseline; none regress past the BENCH-02 threshold.
- Scraper politeness (per-host rate limit + bounded concurrency) is demonstrably preserved.
- No external infrastructure (Redis/Memcached/RabbitMQ) and no on-disk format change introduced.

## Definition of Done

- All v1 requirements implemented and verified.
- All tests green + new benchmark baselines committed + golden-equivalence checks pass.
- Documented before/after numbers for refresh, the key API endpoints, web bundle size, and CLI startup.

## v2 Requirements

Deferred — gated behind the equivalence harness, only if profiling still shows a bottleneck.

### Algorithmic Chemistry (CHEM)

- **CHEM-01**: Make `compute_chemistry` cheaper via precomputed facts (gated behind BENCH-03 equivalence harness)
- **CHEM-02**: Incremental chemistry delta / admissible pruning in build/upgrade search (high risk — tier points are step functions, icons add global league bonus; only if still bottlenecked)

### Data Store (STORE)

- **STORE-01**: Optional SQLite migration of the player store — future milestone, not now

## Out of Scope

| Feature | Reason |
|---------|--------|
| Redis / Memcached | Single-process; in-proc dict is faster than an out-of-process cache here |
| RabbitMQ / task broker | Single-user, single-node; no distribution problem to solve |
| Behavior / output changes | Dad's authoritative tool — outputs must stay identical |
| On-disk format change (now) | Keep JSON; cache solves the read cost without rewriting the data layer |
| New features | Performance-only milestone |

## Traceability

Every v1 requirement maps to exactly one phase. See `.planning/ROADMAP.md` for phase detail.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BENCH-01 | Phase 1 | Pending |
| BENCH-02 | Phase 1 | Pending |
| BENCH-03 | Phase 1 | Pending |
| BENCH-04 | Phase 1 | Pending |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 2 | Pending |
| API-01 | Phase 3 | Pending |
| API-02 | Phase 3 | Pending |
| API-03 | Phase 3 | Pending |
| SCRAPE-01 | Phase 4 | Pending |
| SCRAPE-02 | Phase 4 | Pending |
| SCRAPE-03 | Phase 4 | Pending |
| SCRAPE-04 | Phase 4 | Pending |
| WEB-01 | Phase 5 | Pending |
| WEB-02 | Phase 5 | Pending |
| WEB-03 | Phase 5 | Pending |
| CLI-01 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18 (100%)
- Unmapped: 0

*v2/deferred (CHEM-01, CHEM-02, STORE-01) intentionally not mapped — remain deferred.*

---
*Requirements defined: 2026-06-17*
*Last updated: 2026-06-17 after roadmap creation (traceability populated)*
