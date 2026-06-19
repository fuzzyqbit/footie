# Phase 3 Research — API Responsiveness

**Phase:** 3 · **Requirements:** API-01, API-02, API-03
**Date:** 2026-06-19 · **Confidence:** HIGH
**Primary source:** `.planning/research/BACKEND-COMPUTE.md` (full design: GIL/threadpool distinction, file:line fixes, Tier 1 vs Tier 2 risk split, equivalence plan). This distills it to the Phase 3 build + Validation Architecture.

## What Phase 2 already did (don't redo)
BACKEND-COMPUTE Tier-1 #1 (cache the card pool keyed on mtime; build `by_id` once; stop multi-`find_all` per request) is **DONE in Phase 2** — `fc26/db.py` now serves `find_all` from a process-global cache and `find_by_id` is O(1). So Phase 3 is the **remaining** Tier-1 safe wins (#2, #3, #4, #6). Tier-2 (true incremental chemistry, pruning) stays deferred as CHEM v2.

## Phase 3 scope (all Tier-1, output-identical; guarded by the Phase 1 golden)

### API-01 — get CPU/blocking work off the event loop (BACKEND-COMPUTE #3)
Handlers are `async def` but call blocking sync compute directly (`app.py:157-459`), so one slow `/api/build` stalls every concurrent request. Fix (the research's recommended split):
- **GET read endpoints → plain `def`** (FastAPI/Starlette auto-runs them in the anyio threadpool, ~40 workers): `list_cards` (157), `get_card` (219), `list_squads` (226), `get_squad` (231), `get_meta` (328), `get_objectives` (345), `get_sbcs` (371), `get_updates` (384), `get_value` (415). Leave `serve_spa` (469, light I/O) and the async exception handlers as-is.
- **POST/PUT handlers → keep `async def`, offload the blocking body** via `await run_in_threadpool(...)` (Starlette): `put_squad` (245), `post_chem` (256), `post_boost` (265), `post_upgrade` (279), `post_build` (293). They use `await request.json()` (can't be sync); keep the thin async shell that reads the body, then run the pure compute in the threadpool. Preserves exact existing validation/error paths and messages.
- **GIL reality:** under default CPython 3.14 this frees the loop for *other* requests; it does NOT make a single build faster. Single-request latency comes from API-02. No `multiprocessing` (barred + pickling the pool dwarfs compute).
- **Risk:** none — same pure functions, just on a worker thread. The Phase-2 repo cache is already thread-safe (RLock + immutable snapshots). Golden API tests (TestClient) confirm byte-identical responses.

### API-02 — memoize leaf functions + hoist hot-loop invariants (BACKEND-COMPUTE #2, #6)
Two parts:
1. **Memoize (zero risk):** `@lru_cache(maxsize=None)` on `slugify` (`models.py:98`) and `canonical_league`/`canonical_nation`/`canonical_club` (`aliases.py:59-76`). Pure `str→str` maps over a bounded vocabulary (≤ few thousand distinct strings). Called low-millions of times per `/api/build`. This automatically speeds `compute_chemistry` (calls canonical_* at `engine.py:99,104,113,131-135`), `_same_player` (`upgrade.py:61`), and `make_card_id` — **without touching their algorithms**. `lru_cache` is thread-safe in CPython.
2. **Hoist invariants in `find_upgrades` (`upgrade.py:103-161`) — low risk, output MUST stay identical:**
   - **Eligible-by-position buckets:** precompute once `eligible[position] -> tuple[Card,...]` = priced + position-eligible cards, **iterating the pool in original order** so the inner loop scans ~hundreds not 2,434. Replaces the per-round `price is None` (`:114`) + position checks (`:116`).
   - **`(card_id, position) -> meta_score` table:** precompute for eligible pairs (meta_score is pure, `meta.py:41`); replaces `meta_score(candidate, position)` recompute every round (`:129`). Also reuse for `out_meta` (`:112`).
   - **Per-round current-XI slug list:** precompute the current players' slugs once per round; for each candidate run the `_same_player` **prefix check** (`:120-124`) against that small 11-item list instead of re-slugifying both sides per comparison. **Keep the prefix semantics exactly** (`_same_player` is not pure slug equality — `:62-64` matches token-boundary prefixes; `rodri` must NOT match `rodrigo-de-paul`).
   - **CRITICAL invariants:** preserve candidate **iteration order** (the tie-break `delta == best.score_delta and cost < best.net_cost`, `:137-139`) and the `_same_player` prefix logic. Order-preserving filters are safe; any sort/reorder would be an algorithmic change (out of scope). `compute_chemistry`'s algorithm is **unchanged** (just faster via memoized leaves).
   - **Risk:** low but real (output equivalence). Guarded by the Phase 1 golden `builder_matrix.json` + `api_build.json` + `api_upgrade.json` and the benchmark (must be faster, byte-identical).

### API-03 — cache `/api/meta` (BACKEND-COMPUTE #4)
`get_meta` (`app.py:327-342`) rescans the pool for 4 sorted-unique sets every call. Cache the result dict, module-level, keyed on `db_path.stat().st_mtime_ns` (a refresh's atomic `os.replace` bumps mtime → self-invalidates), guarded by a `threading.Lock`. Belt-and-suspenders: explicitly clear the meta cache (and it's fine to leave the repo cache to its own mtime/size check) at the end of the auto-refresh loop (`app.py:86-97`).
- **Byte-identical caveat:** original filters falsy on `leagues`/`nations`/`clubs` (`:331-333`) but **NOT** on `versions` (`:334`). The cached version must mirror this exactly. `FORMATIONS`/`available_styles()` are constants.
- **Risk:** none with mtime key + explicit bust + matching predicates. Golden `api_meta.json` confirms.

## Hard constraints
Byte-identical output (golden is the gate); all existing tests green; no new infra; no on-disk format change. compute_chemistry algorithm untouched (Tier-2 deferred).

## Validation Architecture

> nyquist_validation `true` — section included.

### Test framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8 (+ pytest-benchmark from Phase 1) |
| Quick run | `FORCE_COLOR= NO_COLOR=1 pytest -q` (must stay green; esp. test_api, test_upgrade/test_build, test_chem) |
| Equivalence gate | `FORCE_COLOR= NO_COLOR=1 pytest -m golden --run-bench` (builder_matrix + api_build/upgrade/meta byte-identical) |
| Speed gate | `FORCE_COLOR= NO_COLOR=1 pytest -m benchmark --run-bench --benchmark-storage=.benchmarks --benchmark-compare=0002 --benchmark-compare-fail=mean:10%` then re-baseline; expect /api/build, /api/upgrade, find_upgrades, /api/meta faster, nothing regressed |

### Phase requirements → test map
| Req | Behavior | Test type | Command | Exists? |
|-----|----------|-----------|---------|---------|
| API-01 | Blocking handlers run off the event loop (GET sync def; POST run_in_threadpool); responses identical | unit + concurrency | `pytest tests/test_api.py -q`; new test asserts a slow request doesn't block a concurrent one | partial (test_api) + ❌ W0 concurrency test |
| API-02 | slugify/canonical_* memoized; find_upgrades hoists invariants; build/upgrade output identical + faster | golden + bench + unit | golden builder_matrix/api_build/api_upgrade; benchmark vs 0002; lru_cache present | ✅ golden + ❌ W0 cache-присутствие test |
| API-03 | /api/meta cached on mtime, busted on refresh, byte-identical (versions unfiltered) | golden + unit | golden api_meta; new test: same response across calls + reload after file change | ✅ golden + ❌ W0 meta-cache test |
| (all) | existing tests green; golden byte-identical; benchmark no regression | regression | `pytest -q` + golden + benchmark gate | ✅ existing + Phase 1 |

### Wave 0
- `tests/test_api_perf.py` (or extend test_api): (1) `/api/meta` cache returns identical dict and reloads after the DB file changes; (2) `slugify`/`canonical_*` have `cache_info()` (memoized); (3) a concurrency smoke that a long POST doesn't serialize a concurrent GET (best-effort, may be timing-light).
- Golden equivalence (Phase 1) is the primary safety net for the find_upgrades hoist — no new golden needed (builder_matrix + api already cover it); regenerate ONLY if an intended output change occurs (there must be none).

## Security domain
No new runtime surface (no new endpoints/auth/input/network/crypto). Moving handlers to the threadpool introduces shared-state concurrency — mitigated: repo cache (Phase 2) is RLock-guarded + immutable snapshots; the new /api/meta cache uses its own `threading.Lock`; `lru_cache` is thread-safe. ASVS: none applicable.

## Sources
- `.planning/research/BACKEND-COMPUTE.md` (primary — Tier 1/2 split, GIL/threadpool, equivalence plan; sources incl. Starlette threadpool docs, Python 3.14 free-threading docs).
- Code (read directly): `fc26/api/app.py` (handlers, lifespan/refresh loop), `fc26/builder/upgrade.py` (find_upgrades, _same_player, tie-break), `fc26/builder/meta.py` (meta_score), `fc26/models.py:98` (slugify), `fc26/chem/aliases.py:59-76` (canonical_*), `fc26/chem/engine.py` (compute_chemistry — unchanged).
- Phase 1 harness golden + `.benchmarks/0002` (Phase 2 baseline).
