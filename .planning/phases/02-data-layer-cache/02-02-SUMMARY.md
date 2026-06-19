# Plan 02-02 Summary — Apply Batch + Prove the Win

**Status:** Complete · **Requirements:** DATA-03 (realized)

## What was built
- `fc26/ingest/refresh.py` — `refresh_data` wraps the `expand_cards` + `enrich_cards` body in one `with repo.batch():`, so the ~2,400 upserts defer to a single flush. Covers `fc26 refresh` and the API auto-refresh loop. Manifest block stays outside the batch.
- `fc26/cli.py` — `with repo.batch():` added to every looping command: `seed`, `sync` (~100 cards), `enrich`, `expand`, `images`. Only single-card `add` left unwrapped. `enrich.py`/`expand.py`/`images.py` untouched (their upsert honors the repo's batch flag — no nesting).
- `tests/test_refresh.py` — stub repo updated with a no-op `batch()` (refresh_data now uses the batch interface).
- `tests/benchmarks/test_bench_refresh.py` — added `test_bench_bulk_upsert_batched` (the real refresh write pattern) alongside the non-batch bench.
- `.benchmarks/0002` — new post-Phase-2 baseline committed (Phase 3 compares against this).

## Verification
- `pytest -q` → 348 passed, 28 skipped (unchanged behavior).
- `pytest -m golden --run-bench` → 10 passed (**byte-identical**: refresh_players.json, API, CLI, build).
- `pytest tests/test_refresh.py tests/test_expand.py tests/test_enrich.py tests/test_images.py tests/test_cli.py` → green (counts / new-vs-merged / id-suffix / single-writer invariants preserved).

## Before → After (mean, ro-HEAD `0001` baseline → Phase 2)
| Path | Before | After | Change |
|------|--------|-------|--------|
| `find_all` | 673 µs | 3.3 µs | **~200× faster** (cache) |
| `find_by_id` | 672 µs | 3.4 µs | **~200× faster** (O(1) index) |
| `/api/meta` | 1343 µs | 656 µs | ~2× |
| `/api/cards` | 1867 µs | 1181 µs | ~1.6× |
| `/api/upgrade` | 9937 µs | 8540 µs | ~1.16× |
| bulk upsert (non-batch) | 47.3 ms | 24.9 ms | ~1.9× (no per-upsert re-parse) |
| **bulk upsert (batched)** | — | **0.97 ms** | **~26× vs non-batch** — the refresh win |
| `upsert_one` (single, non-batch) | 1464 µs | 1656 µs | **+13% (fsync durability cost)** |
| `find_upgrades`, `/api/build` | ~same | ~same | compute-bound → Phase 3 |

## Decision: the `upsert_one` +13% is accepted
The single-write regression is the deliberate `fsync(file)` + `fsync(parent dir)` durability cost added to `_atomic_write` (the old code could lose data on power loss). It only affects a single NON-batched write (the rare `add` command). Every real loop now batches → one fsync per run, not per card — which is why batched refresh is ~26× faster. The `--benchmark-compare-fail=mean:10%` gate vs `0001` flags only this one micro-op; that is expected. Re-baselined to `0002` so Phase 3's gate is meaningful.

## Notes
- Reads being ~200× faster at corpus size understates the real-DB win (2,434 cards / 4.4 MB) — the `live`-gated `test_bench_find_all_real_db` (run with `--run-live`) shows it at production scale.
