# Phase 2 Research — Data-Layer Cache & Batched Writes

**Phase:** 2 · **Requirements:** DATA-01..04
**Date:** 2026-06-18 · **Confidence:** HIGH
**Primary source:** `.planning/research/CACHING.md` (implementation-ready design with code sketches, invalidation strategy, risk register, verification plan, file:line citations). This file distills it into the Phase 2 build + Validation Architecture. Read CACHING.md for full detail.

## Goal recap
Make `fc26/db.py` reads serve from an in-process, id-indexed cache (no per-call full re-parse) and make refresh writes batched + atomic + durable (one write per run, not O(n²) per-card) — **with byte-identical output and all behavior preserved** (Phase 1 golden + the existing `test_db`/`test_expand`/`test_enrich`/`test_images` suites are the contract).

## The design (from CACHING.md)
- **Process-global cache keyed by `path.resolve()`**, NOT per-instance — `app.py` builds a fresh `CardRepository(db_path)` in ~12 handlers; a per-instance cache would re-parse every request. Each `CardRepository` is a thin handle onto a shared `_CacheEntry` (cards snapshot tuple + `by_id` index + mtime + size + dirty + RLock). (DATA-01)
- **Read path** `_ensure_loaded()`: reload only when file mtime **or** size changed since last load; otherwise serve from RAM. `find_all` returns the immutable snapshot tuple (DATA-04 — `enrich_cards` iterates `find_all()` while upserting inside the loop, `enrich.py:57`+`:86`, so a live/mutable view would change behavior). `find_by_id` becomes O(1) via the index (was O(n) scan, `db.py:62-66`). `search` runs identical fold/alias logic over the cached snapshot. (DATA-01)
- **Invalidation** (DATA-02): mtime+size re-stat on every read detects external/CLI writes (CLI-writes-while-server-runs); re-stat **after** self-write so we don't redundantly reload our own bytes; `dirty` wins over disk so a batched refresh reads its own in-memory state mid-stream. Both mtime AND size tracked (coarse 1s mtime edge case). The in-process auto-refresh writes through the same path-keyed entry, so event-loop readers see new data on next `_ensure_loaded`.
- **Write path** (DATA-03): `upsert` mutates the cached index (build a NEW dict/tuple, never mutate the iterated one), keeps `validate_card` + `merge_cards` boundaries identical (`db.py:86-91`), keeps the id-sort on the snapshot so on-disk byte order is unchanged (`db.py:99`). Default (non-batch) flushes every upsert → byte-identical to today. A `batch()` context defers the write to a single `flush()` (flushes on exception too, so a partial scrape still persists).
- **Atomicity + durability**: keep temp→`os.replace`, ADD `fsync(file)` + `fsync(parent dir)` guarded for non-POSIX (the current `_atomic_write` lacks fsync, `db.py:104-114`). Batching makes fsync cost negligible (one per run, not 2,400).

## Batch application sites (where the O(n²)→O(n) win is realized)
Wrap `with repo.batch():` at the orchestration layer (do NOT nest — `batch()` is not re-entrant):
- `refresh_data` (`fc26/ingest/refresh.py:51-69`) — wrap the `expand_cards` + `enrich_cards` body. The same `repo` instance is passed down, so their `upsert` loops (`expand.py:69`, `enrich.py:86`) defer. Covers both `fc26 refresh` and the API auto-refresh loop. The manifest `find_by_id` loop (`refresh.py:73-76`) becomes O(1) automatically.
- `fc26 seed` loop (`cli.py:82`), `fc26 enrich` (calls `enrich_cards`), `fc26 expand` (calls `expand_cards`), `fc26 images` (calls `images.upgrade` whose serial main-thread upsert is `images.py:215`) — wrap each CLI command's call so standalone commands also batch.
- `enrich.py`/`expand.py`/`images.py` themselves need NO change — their `upsert` already checks the repo's batch flag set by the caller.

## Critical invariants / traps (preserve exactly)
- Process-global path-keyed cache (per-instance defeats the API win). **CRITICAL.**
- `find_all` returns an immutable snapshot (iterate-while-upsert). **CRITICAL.**
- Byte-identical save: keep `sorted(..., key=lambda c: c.id)` + `json.dumps(ensure_ascii=False, indent=2) + "\n"`. **CRITICAL** (Phase 1 `refresh_players.json` golden asserts these bytes).
- `merge_cards` on id-collision + `_resolve` id-suffix (`expand.py:84-97`) must behave identically against the cached `by_id`.
- Thread-safety: per-entry `RLock` (auto-refresh worker thread vs event-loop reads — the one true concurrency point in `serve`). Keep image upsert single-threaded (`test_images.py:181`).
- Test isolation: process-global cache keyed by resolved path keeps tmp_path repos isolated; add a private `_reset_cache()` hook + autouse fixture if any cross-test bleed appears (tests reuse paths / force mtimes).

## Validation Architecture

> nyquist_validation is `true` — section included.

### Test framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8 (+ pytest-benchmark from Phase 1) |
| Quick run | `NO_COLOR=1 pytest -q` (must stay green; existing db/expand/enrich/images contract) |
| Equivalence gate | `NO_COLOR=1 pytest -m golden --run-bench` (Phase 1 golden — byte-identical players.json, API/CLI/build output) |
| Speed gate | `NO_COLOR=1 pytest -m benchmark --run-bench --benchmark-storage=.benchmarks --benchmark-compare=0001 --benchmark-compare-fail=mean:10%` then re-baseline; expect find_by_id/refresh much faster, nothing regressed |

### Phase requirements → test map
| Req | Behavior | Test type | Command | Exists? |
|-----|----------|-----------|---------|---------|
| DATA-01 | load-once cache + O(1) find_by_id; reads served from RAM | unit + bench | `pytest tests/test_db_cache.py`; bench shows ≥1 parse not N | ❌ Wave 0 (`tests/test_db_cache.py`) |
| DATA-02 | mtime+size invalidation (external write reloads; self-write no redundant reload) | unit | `pytest tests/test_db_cache.py -k invalidat` | ❌ Wave 0 |
| DATA-03 | batched upsert → exactly one write per batch; fsync called; refresh bench faster | unit + bench | `pytest tests/test_db_cache.py -k batch`; refresh benchmark | ❌ Wave 0 |
| DATA-04 | find_all immutable snapshot stable across upsert | unit | `pytest tests/test_db_cache.py -k snapshot` | ❌ Wave 0 |
| (all) | existing db/expand/enrich/images tests stay green; golden byte-identical | regression | `pytest -q` + `pytest -m golden --run-bench` | ✅ existing + Phase 1 golden |

### New tests (CACHING.md §Verification)
1. mtime/size invalidation (external rewrite reloads; same size+mtime different bytes still reloads via size or content). 2. self-write no redundant reload (count parses; N upserts in `batch()` → 1 parse + 1 write). 3. snapshot stability (held tuple unchanged after upsert). 4. concurrency smoke (thread upserts while main find_all loops). 5. fsync called (monkeypatch os.fsync count). 6. byte-identical output (covered by Phase 1 `test_golden_refresh`).

### Wave 0
- `tests/test_db_cache.py` — the 5 cache-specific tests above.
- `CardRepository._reset_cache()` private hook + autouse fixture if cross-test bleed appears (process-global cache).

## Security domain
db.py change adds NO runtime surface (no endpoints/auth/input/network/crypto). Only consideration: the cache is process-local state — no new persistence, no secrets. The RLock prevents a read-modify-write race under the auto-refresh worker (correctness, not security). ASVS: none applicable.

## Sources
- `.planning/research/CACHING.md` (primary — full design + sources: python-atomicwrites, os.replace/fsync semantics, FastAPI concurrency).
- Codebase (read directly): `fc26/db.py:42-114`, `fc26/ingest/{refresh.py,enrich.py,expand.py,images.py}`, `fc26/cli.py`, `fc26/api/app.py` (~12 repo constructions).
- Phase 1 harness: `.benchmarks/0001_…` baseline, `tests/benchmarks/test_golden_refresh.py` (byte gate).
