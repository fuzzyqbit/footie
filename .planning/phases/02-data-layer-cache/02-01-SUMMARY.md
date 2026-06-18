# Plan 02-01 Summary — db.py Cache + Batched/Durable Writes

**Status:** Complete · **Requirements:** DATA-01, DATA-02, DATA-03 (mechanism), DATA-04

## What was built
- `fc26/db.py` rewritten with a **process-global cache keyed by `path.resolve()`** (`_CACHES` + `_CacheEntry`), shared across the per-request/per-command `CardRepository` instances:
  - **DATA-01** — load-once: `_parse_file` is the only `json.loads`; `find_all` serves the cached snapshot; `find_by_id` is O(1) via the `by_id` index.
  - **DATA-02** — `_ensure_loaded` reloads only when file mtime OR size changed; `_flush_locked` re-stats after a self-write so our own bytes don't trigger a redundant reload; `dirty` wins over disk inside a batch.
  - **DATA-03 (mechanism)** — `upsert` mutates the cache + flushes (immediately by default); `batch()` context defers to one `flush()` (flushes on exception too); `_atomic_write` now fsyncs the temp file + parent dir (POSIX-guarded via `_fsync_dir`).
  - **DATA-04** — `find_all` returns an immutable snapshot tuple; `upsert` builds a NEW dict/tuple, never mutating the held reference (iterate-while-upsert preserved).
- Public API unchanged; `_save` kept byte-identical (id-sort, `indent=2`, `ensure_ascii=False`, trailing newline); `validate_card` + `merge_cards` boundaries unchanged; original `DatabaseError` semantics preserved in `_parse_file`.
- Added `CardRepository._reset_cache()` test hook.
- `tests/test_db_cache.py` — 7 tests: external-write invalidation, size-change-with-pinned-mtime reload, one-parse/one-write per batch, per-upsert writes without batch, snapshot stability, concurrency smoke, fsync-on-flush.

## Verification
- `pytest tests/test_db.py tests/test_search.py tests/test_expand.py tests/test_enrich.py tests/test_images.py -q` → 49 passed (contract preserved unedited).
- `pytest tests/test_db_cache.py -q` → 7 passed.
- `pytest -q` → 348 passed, 27 skipped (was 341 + 7 new).
- `pytest -m golden --run-bench` → 10 passed (**byte-identical** players.json / API / CLI / build).

## Notes
- mtime+size invalidation has the known blind spot of a same-mtime **and** same-size different-content write (extremely rare); standard for this approach. Realistic CLI/refresh writes change size or mtime → detected.
