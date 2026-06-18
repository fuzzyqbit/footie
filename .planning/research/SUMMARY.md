# Performance Milestone — Research Synthesis

**Synthesized:** 2026-06-17
**Inputs:** `CACHING.md`, `ASYNC-SCRAPING.md`, `BACKEND-COMPUTE.md`, `FRONTEND-TOOLING.md` (+ `PROJECT.md`, `codebase/CONCERNS.md`)
**Milestone:** Make footie faster (refresh, API, web load) with **zero observable behavior change** — same `data/players.json` bytes, same API responses, same CLI text, all tests green.
**Overall confidence:** HIGH on direction and mechanism; LOW on absolute numbers (no profiling data exists yet — the harness produces them).

---

## 1. TL;DR

- **One root cause dominates everything.** The "DB" is a single ~4.4 MB JSON file (`data/players.json`, ~2,434 cards). `fc26/db.py` re-reads/re-parses the whole file on nearly every read and re-serializes+rewrites the whole file on **every** `upsert` — driving both the O(n²) refresh and the per-request re-parse on every API call.
- **Four researchers independently converged on the same order:** (1) build the measurement harness first, (2) add an in-process read cache + batched writes over `db.py` — the single biggest, lowest-risk win that unblocks both API and refresh, (3) get blocking compute off the event loop + safe memoization, (4) async scraper rewrite, (5) frontend code-splitting + React Query tuning + CLI lazy imports.
- **Hard constraint runs through every phase:** outputs byte-identical, all tests green, scraper politeness preserved, no new infra (no Redis/SQLite/process pool). Several specific output-equivalence traps were flagged (below) and must be guarded by the harness.
- **The work cleanly splits into provably-equivalent mechanical wins (ship freely) and algorithmic changes gated behind an equivalence harness (chemistry deltas / candidate pruning — optional, only if profiling still warrants).**

---

## 2. Cross-cutting prerequisite — the benchmark/profiling harness (lands FIRST)

Every researcher said the same thing: **no latency/throughput baseline exists today** (`pyproject.toml` dev extras are only `pytest`/`pytest-cov`; no `pytest-benchmark`, no `cProfile`, no `perf_counter` harness). This harness is simultaneously the **measurement instrument** (proves each change is faster) and the **behavior-equivalence safety net** (golden-output diffing catches any byte/output drift). Nothing optimized ships before it.

**Tooling (verified, FRONTEND-TOOLING B1):**
- **pytest-benchmark** — committed baselines + CI-style regression gate (`--benchmark-save`, `--benchmark-autosave`, `--benchmark-compare`, `--benchmark-compare-fail mean:10%`). The durable safety net. Gate behind a `benchmark` marker mirroring the existing `live` marker so the default `pytest` run stays fast.
- **cProfile** (+ snakeviz/gprof2dot) — one-shot "where does the time go" call-graph attribution before/after a change.
- **py-spy** — sample the live `fc26 serve` / async refresh process (attaches to a PID, no restart).

**What it measures (first baselines, tied to CONCERNS hot paths):**
- `CardRepository.find_all()` full load+parse of the real DB (CONCERNS 1.x/3.1) — cache must beat this.
- `CardRepository.upsert()` single card into a populated DB (CONCERNS 1.1) — batched write must beat this; assert `_atomic_write` call count drops ~2,400 → 1.
- Full `refresh_data` with **mocked HTTP + stubbed sleep** (offline) (CONCERNS 1.1/1.2/1.5) — proves async + batch win without network variance.
- `compute_chemistry` single call; `find_upgrades` one `/api/upgrade`-shaped call; `build_squad` one `/api/build`-shaped call (CONCERNS 3.5/3.6).
- `/api/cards?limit=5000` and `/api/meta` via `TestClient` (CONCERNS 3.1/3.2/3.3).
- CLI startup: `python -X importtime -m fc26 --help` before/after (CONCERNS 4.1).

**Equivalence side of the harness (the safety net):** capture **golden outputs** before any change — a fixtured refresh produces `players.json` bytes + `ExpandResult`/`EnrichResult`/`ImagesResult` tuples + progress-line sequence; a build/upgrade matrix (every formation × both objectives × several budgets) serialized via `asdict`. Re-assert structural equality after each change. This is the gate that enforces "zero behavior change."

**Discipline:** capture baselines on `ro` HEAD first, commit the JSON, then `--benchmark-compare-fail` on every subsequent change. Start loose (`mean:10%`) to avoid laptop flakiness; tighten once stable.

---

## 3. Sequenced work, risk-ordered (recommended build order)

This is the convergent ordering across all four files. Impact and risk are per item; file:line citations are the researchers'.

| # | Work item | Impact | Risk | Key citations |
|---|-----------|--------|------|---------------|
| **0** | **Benchmark + golden-equivalence harness** (Section 2) | — (enabler) | None | `pyproject.toml:16`; no harness exists |
| **1** | **In-process read cache over `db.py`** — load-once, index by id, reload on mtime+size change. **Process-global, keyed by `path.resolve()`** (a per-instance cache is defeated by the ~12 per-request `CardRepository(db_path)` constructions). `find_all` returns the **immutable snapshot tuple** as today; `find_by_id` becomes O(1). | **HIGH** | **Low** | `db.py:48,62-66,85`; `app.py:186,220,259,…` |
| **2** | **Batched + atomic+durable writes** — replace per-`upsert` full rewrite with in-memory dict mutation + a single deferred `_save()` via a `batch()` context (wrap `refresh_data`, `enrich_cards`, `expand_cards`, `images.upgrade`, `cli seed`). Add `fsync` (file + parent dir, POSIX-guarded) the current `_atomic_write` lacks. Default (non-batched) path still flushes every upsert → byte-identical; batching is the O(n²)→O(n) refresh win. | **HIGH** | **Low** | `db.py:85-114`; `refresh.py:41`; `enrich.py:57-103`; `expand.py:60-71`; `images.py:206-268` |
| **3** | **Get blocking compute off the event loop** — sync `def` for GET handlers (auto-offload to anyio threadpool); thin async shell + `run_in_threadpool` for POSTs (`/api/build`, `/api/upgrade`, `/api/chem`, `/api/boost`) to preserve exact body-parsing/error paths. Keeps the server responsive under a slow build. | **MED** (throughput/responsiveness; **not** single-request latency under GIL) | **Low** | `app.py:255-459`; auto-refresh already correct at `app.py:89` |
| **4** | **Safe memoization + per-call cost reduction** — `lru_cache` on pure `slugify`/`canonical_club/league/nation`; cache `/api/meta` keyed on pool mtime (+ explicit bust on refresh); precompute per-card chem facts (canonical keys, `is_icon`/`is_hero`, slug) once per pool load; order-preserving eligible-by-position buckets and a `(card,pos)→meta_score` table hoisted out of `find_upgrades`. | **MED–HIGH** | **Low** (order + `_same_player` prefix semantics must be preserved) | `models.py:98`; `aliases.py:59-76`; `app.py:327-342`; `engine.py:78-160`; `upgrade.py:103-161` |
| **5** | **Async scraper rewrite** — shared `httpx.AsyncClient` (pool reuse) + `asyncio.Semaphore` (concurrency cap) + per-host `HostRateLimiter` (preserves the `sleep(1.0)` politeness, per host) + manual 1-retry-on-any-HTTPError wrapper (transport `retries=` only covers connect errors). **Concurrent fetch/parse, serial upsert** (mirrors the proven `images.py` single-writer rule). Ship **enrich + images first** (the 2,000+-card loops), then `expand` with bounded page look-ahead. Bridge CLI via `asyncio.run`, FastAPI via `to_thread(asyncio.run(...))`. | **HIGH** (refresh is dominated by serial sleeps) | **Med** (ordering/equivalence; concurrency/interval numbers need tuning) | `web.py:18,24`; `enrich.py:51-126`; `expand.py:46-95`; `images.py:230-268`; `refresh.py:29-32`; `app.py:75-101` |
| **6** | **Frontend code-splitting + React Query tuning** — route-level `React.lazy` + `Suspense` (one chunk per page; finally makes GeneratorPage's existing `@imgly` dynamic import pay off); `manualChunks` object-form vendor split (Vite 6 → `rollupOptions`, **not** `rolldownOptions`); set sane `QueryClient` `defaultOptions` (`staleTime` 5min, `gcTime` 30min, `refetchOnWindowFocus:false`). | **HIGH** (initial bundle) / **MED** (refetch noise) | **Low** | `App.tsx:3-13`; `GeneratorPage.tsx:272`; `main.tsx:8`; `cards.ts:49-55`; `vite.config.ts` |
| **7** | **CLI lazy imports** — move heavy module-level imports (httpx, rich, selectolax, builder/chem/ingest graph) into the command bodies that use them; make `Console(width=200)` lazy. `serve` already defers uvicorn — follow that pattern. | **MED** (`--help`/simple-command startup) | **Low** | `cli.py:11-36,39,715-716` |
| **8** | **GATED: algorithmic chemistry changes** — true incremental single-swap chemistry delta and/or admissible candidate pruning. **Only behind the full equivalence harness, only if profiling shows `compute_chemistry`/`find_upgrades` is still the bottleneck after #4.** Never bundled with the safe wins. | HIGH (if needed) | **HIGH** | `engine.py:78-160`; `upgrade.py:113-153`; `rules.py:15-21` |

**Sequencing logic:** #1+#2 are the same `db.py` change set and likely remove the majority of wall-clock cost on day one — even without batching, the read cache alone collapses each upsert's `find_all()` re-parse to a no-op. #3 is orthogonal (correctness/responsiveness) and can land anytime after #1. #4 builds on the cached pool. #5/#6/#7 are independent tracks that can parallelize once the harness (#0) is green. #8 is optional and last.

---

## 4. Hard constraints carried into every phase

From `PROJECT.md` Constraints — non-negotiable in all phases:

- **Outputs byte-identical** — same `data/players.json` format (incl. id-sorted on save, `db.py:99`), same API responses, same CLI text.
- **All existing tests stay green** — ~346 pytest + vitest + Playwright e2e are the correctness floor; the benchmark suite is a separate speed gate. Neither is sacrificed; don't edit a behavioral test to make an optimization pass.
- **Scraper politeness preserved** — per-host ~1 req/s, bounded concurrency, jitter, honest User-Agent. Expose `concurrency`/`min_interval` as conservative parameters tuned only against the harness.
- **No new infra** — no Redis/Memcached/RabbitMQ (out-of-process cache adds latency at single-process scale); no SQLite (deferred to a future phase); no `multiprocessing`/process pool (pickling the 2,434-card pool dwarfs the compute and is barred by the constraint). In-process + algorithmic only.

**Specific output-equivalence traps the researchers flagged (guard each in the harness):**
- **Concurrent upsert corruption → single writer.** `db.upsert` is read-modify-write over the whole file with `merge_cards`; two simultaneous upserts lose an update. Fetch/parse concurrently, **upsert serially in card order** (`db.py:85-93`; mirrors `images.py` single-writer rule).
- **`expand._resolve` id-suffix order dependence.** Suffixes a card's id on ovr collision using `find_by_id` of prior cards — out-of-order/parallel processing changes ids. Keep `expand` page-ordered and upserted sequentially even with look-ahead (`expand.py:82-95`).
- **`/api/meta` version-filter falsy quirk.** Original computes `versions = sorted({c.version for c in all_cards})` with **no** truthiness filter, while `leagues`/`nations`/`clubs` **do** filter falsy. The cached meta must replicate this exactly (`app.py:327-342`).
- **Tier-point step functions make incremental chemistry non-local.** `CLUB/NATION/LEAGUE_TIERS` are threshold step functions, plus icon-league global +1, hero/icon 2× weights, per-player cap, manager bonus — a single swap can shift any sharer across a threshold. This is why incremental chemistry (#8) is HIGH risk and must be parity-swept (`rules.py:15-21`; `engine.py:90-140`).
- Also: `find_all` must return an **immutable snapshot** (iterate-while-upsert in `enrich.py:57`+`:86`); self-write must re-stat to avoid a redundant reload; `_same_player` is **prefix-aware**, not pure slug equality (`upgrade.py:52-64`); candidate **order** must be preserved for the `score_delta`/`net_cost` tie-break (`upgrade.py:137-139`).

---

## 5. Quick wins vs gated work

**Quick wins — provably/mechanically equivalent (ship freely once the harness can prove "faster"):**
- In-process read cache + O(1) `by_id` index (#1).
- Batched + fsync'd atomic writes (#2) — default path unchanged; batch context is the only new behavior, byte-identical output.
- Event-loop offload via sync `def` / `run_in_threadpool` (#3) — offloads the *existing* pure functions.
- `lru_cache` on pure `slugify`/`canonical_*`; `/api/meta` mtime-keyed cache; precomputed per-card chem facts; order-preserving eligibility buckets (#4).
- Frontend `React.lazy` split, `manualChunks` vendor split, QueryClient `defaultOptions`, dead-dep removal (#6).
- CLI deferred imports (#7).
- Async scraper (#5) is *mechanically* sound but carries ordering hazards, so its golden diff (bytes + result tuples + progress sequence) is the gate before flipping the default to async.

**Gated work — needs the equivalence harness as a hard gate:**
- True incremental single-swap chemistry delta (#8) — parity sweep over thousands of random swaps + threshold/icon/hero/manager edge cases; property test if `hypothesis` is acceptable as a dev dep.
- Admissible candidate pruning (#8) — only a *provable* upper bound, never a heuristic top-N (a low-meta card can win on chem via `CHEM_WEIGHT=3.0`).
- `useAllCards` payload trimming (optional/stretch) — changes what the client receives; gate on e2e. The backend cache is the bigger lever here anyway.

---

## 6. Notable findings

- **Dead dependency `html-to-image`** (`web/package.json:19`) — declared but **never imported**; PNG export is hand-rolled via `canvas.toDataURL` (`GeneratorPage.tsx:402`). Removable (supply-chain/install-weight win; bundle-byte delta likely ~0 since tree-shaking already excludes it — verify with a build-size diff).
- **`@imgly/background-removal` is already dynamically imported** (`GeneratorPage.tsx:272`) — no change needed there; it just needs the **page** lazy-loaded (#6) for the WASM/model chunk to leave the initial download.
- **Verified versions (not training memory):** httpx **0.28.1** (`Limits`/`Timeout`/`AsyncClient` defaults confirmed by `inspect` of the installed wheel; transport `retries=` covers connect errors only). Python **3.14.5** with the **GIL on by default** → threadpool offload frees the event loop for *other* requests but does **not** speed a single CPU-bound build; single-request latency only improves via memoization/algorithmic/cache work. Vite **6** → `build.rollupOptions.output.manualChunks` (the Rolldown `rolldownOptions.codeSplitting` is Vite 7+ only). TanStack Query v5 defaults (`staleTime:0`, refetch-on-mount/focus) confirm the bare `QueryClient` refetch issue.
- **PEP 810 lazy imports N/A** (lands in 3.15) — the CLI fix is manual deferred imports, not a language feature.

---

## 7. Open questions

- **No profiling data exists yet.** All bottleneck rankings are *structural* (read from source), not *measured*. The harness (#0) must capture `cProfile`/pytest-benchmark numbers on `ro` HEAD before any optimization, especially to decide whether the gated chemistry work (#8) is ever needed after the Tier-1 wins.
- **Cache invalidation edge — CLI writes while server runs.** The mtime+size re-stat is the standard, reasoned defense, but it is **not yet covered by a footie-specific test**. Needs a dedicated test: load via repo A, externally rewrite the file (simulating `fc26 refresh` in another terminal), assert the running server's next read reloads; plus the same-second-write (coarse-mtime) edge guarded by the size check.
- **Async concurrency/interval values (start 4 / 1.0s)** are conservative defaults, not asserted correctness — tune only against the harness, never raise past the current per-host rate without a measured decision.
- **e2e Suspense-fallback timing** — confirm Playwright specs wait on page content, not on spinner absence, after route-splitting introduces a fallback (low risk).
- **`benchmark-compare-fail` threshold** — start loose (`mean:10%`) on a dev laptop; tighten once baselines are stable.

---

## 8. Confidence assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Data-layer caching (read cache + batched writes) | **HIGH** | Direct reads of `db.py`/`app.py`; process-global-keyed requirement is a direct consequence of per-request construction |
| Backend compute (event-loop offload, memoization) | **HIGH** | Direct reads of handlers + builder/chem; GIL/threadpool distinction verified against py3.14 docs |
| Async scraping (mechanism + integration shape) | **HIGH** mechanism / **MEDIUM** exact rate numbers | httpx 0.28.1 introspected from the wheel; concurrency/interval are tuning knobs, not correctness |
| Frontend + tooling | **HIGH** | Vite/Rollup/React/TanStack/pytest-benchmark APIs verified against official docs, tied to file:line |
| Absolute latency/throughput numbers | **LOW** | No profiling captured — this is exactly what the harness (#0) produces |

---

## Recommended phase ordering (for the roadmapper)

1. **Benchmark + equivalence harness** — measurement instrument + golden-output safety net; lands first, nothing optimized ships without it.
2. **Data-layer cache + batched writes** (`db.py`) — biggest, lowest-risk win; collapses per-request re-parse and the O(n²) refresh; unblocks both API and refresh.
3. **API responsiveness + safe memoization** — off-event-loop handlers, `lru_cache` on pure helpers, `/api/meta` cache, precomputed chem facts, order-preserving loop hoists.
4. **Async scraper rewrite** — concurrent fetch / serial upsert, per-host politeness preserved; enrich+images first, then expand look-ahead; flip default only after the golden diff is green.
5. **Frontend load + CLI startup** (parallelizable) — route code-splitting, manualChunks, React Query tuning, dead-dep removal; CLI lazy imports.
6. **(Gated, optional) Algorithmic chemistry** — incremental delta / admissible pruning, only behind the full equivalence harness and only if profiling still warrants.

---

## Sources

Aggregated from the four research files (full lists in each):
- httpx docs (Resource Limits, Transports, Exceptions, Async) + live `inspect` of httpx 0.28.1 in `.venv` (Python 3.14.5).
- python-atomicwrites; Python `os.replace`/`os.fsync` guides; "avoid data corruption by syncing to disk."
- FastAPI/Starlette concurrency + threadpool docs; FastAPI race-condition write-up.
- Python 3.14 free-threading howto + What's New; GIL/asyncio relationship.
- react.dev `lazy`; Vite 6 build docs; Rollup `output.manualChunks`; TanStack Query v5 important-defaults.
- pytest-benchmark usage; "beyond cProfile"; py-spy/cProfile profiling guides; lazy-imports write-ups (PEP 810 context).
- Async rate-limiting/politeness guides (Scrapfly, ProxiesAPI, StudyRaid, The Web Scraping Club).
- **Primary source: the footie codebase** (`fc26/db.py`, `fc26/api/app.py`, `fc26/builder/*`, `fc26/chem/*`, `fc26/ingest/*`, `fc26/cli.py`, `web/src/*`) + `.planning/codebase/CONCERNS.md` + `.planning/PROJECT.md`.
