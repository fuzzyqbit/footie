# Plan 01-02 Summary — Benchmarks + Regression Gate

**Status:** Complete · **Requirements:** BENCH-01, BENCH-02

## What was built
- `tests/benchmarks/test_bench_db.py` — `find_all`, `find_by_id`, single `upsert`; plus a `live`-gated real-DB read bench.
- `tests/benchmarks/test_bench_refresh.py` — bulk-upsert write amplification (the O(n²) whole-file-rewrite-per-card cost Phase 2 fixes). Network fetch stages excluded by design (documented).
- `tests/benchmarks/test_bench_builder.py` — `build_squad` (4-2-3-1 meta, 4-3-3 rating) + `find_upgrades`.
- `tests/benchmarks/test_bench_api.py` — `/api/cards`, `/api/meta`, `/api/build`, `/api/upgrade` via TestClient.
- `.benchmarks/` — committed ro-HEAD baseline (`0001_…`).
- `tests/benchmarks/README.md` — run / save-baseline / regression-gate docs.

## Verification
- `pytest -m benchmark --run-bench` → 11 passed, 1 skipped (live). Baseline saved.
- Regression gate `--benchmark-compare=0001 --benchmark-compare-fail=mean:10%` → **EXIT 0** (green vs baseline).
- `pytest -q` → 341 passed, 17 skipped (unchanged; all bench/golden/live gated off).
- Zero `fc26/` changes.

## Baseline numbers (ro HEAD, mean)
- find_all ~0.67ms · find_by_id ~0.67ms · upsert_one ~1.46ms · api_meta ~1.34ms · api_cards ~1.87ms
- find_upgrades ~7.9ms · api_upgrade ~9.9ms · bulk_upsert ~47ms · build_squad ~44-49ms · api_build ~46ms

These confirm the bottleneck ranking: build/upgrade compute + bulk-upsert dominate; reads are cheap at corpus size (will dominate at real-DB size — see the live bench).

## Notes
- `test_bench_bulk_upsert` is variance-prone (few rounds, large unit) — re-baseline after a *real* Phase 2 improvement rather than chasing single-run noise.
