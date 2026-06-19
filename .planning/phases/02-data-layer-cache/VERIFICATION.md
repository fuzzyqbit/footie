---
phase: 2
slug: data-layer-cache
status: passed
verified: 2026-06-19
---

# Phase 2 Verification — Data-Layer Cache & Batched Writes

Goal-backward check: *reads serve from an in-process id-indexed cache (no per-call full re-parse); refresh writes are batched + atomic + durable (one write per run); byte-identical output, all behavior preserved.*

## Requirement coverage

| Req | Delivered | Evidence |
|-----|-----------|----------|
| DATA-01 | Load-once cache + O(1) `find_by_id` | `fc26/db.py` `_CACHES`/`_entry_for` (path.resolve()), `by_id` index; bench `find_all` 673µs→3.3µs, `find_by_id` 672µs→3.4µs |
| DATA-02 | mtime+size invalidation; self-write no redundant reload | `_ensure_loaded` re-stat + `_flush_locked` re-stamp; `tests/test_db_cache.py` invalidation tests |
| DATA-03 | Batched + atomic + durable writes (O(n²)→O(n)) | `batch()`/`flush()` + fsync(file+dir); applied at `refresh_data` + CLI; batched bulk upsert 0.97ms vs 24.9ms non-batch (~26×) |
| DATA-04 | Immutable snapshot (iterate-while-upsert) | `find_all` returns snapshot tuple; upsert builds new dict/tuple; `test_db_cache.py` snapshot-stability test |

## must_haves

- ✅ Reads served from a process-global path-keyed cache (survives per-request `CardRepository` construction).
- ✅ `find_by_id` O(1); `find_all` immutable snapshot stable across upsert.
- ✅ mtime+size invalidation (external write reloads; self-write doesn't).
- ✅ Default upsert byte-identical; `batch()` defers to one durable write (fsync); flushes on exception.
- ✅ **Zero behavior change:** `pytest -m golden --run-bench` byte-identical (refresh_players.json, API, CLI, build); `pytest -q` 348 passed (was 341 + 7 cache tests); existing db/expand/enrich/images contract green unedited.

## Speed outcome
find_all/find_by_id ~200× faster; `/api/meta` ~2×, `/api/cards` ~1.6×; **batched refresh ~26× faster** than per-card rewrite. Compute paths (`/api/build`, `find_upgrades`) unchanged — Phase 3's target.

## Notes / carry-forward
- `upsert_one` single-write +13% = intentional fsync durability cost; only the non-batched `add` path; accepted and re-baselined to `0002`. The mean:10% gate vs `0001` flags only this micro-op.
- One test edited: `tests/test_refresh.py` stub gained a no-op `batch()` (mock-interface update for the new `repo.batch()` dependency — not a weakened assertion).
- mtime+size invalidation has the standard blind spot of a same-mtime AND same-size different-content write (extremely rare); documented.

**Verdict: PASSED** — cache + batched/durable writes delivered, big speedups proven, output byte-identical.
