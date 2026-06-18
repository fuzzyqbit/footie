---
phase: 1
slug: benchmark-equivalence-harness
status: passed
verified: 2026-06-18
---

# Phase 1 Verification — Benchmark & Equivalence Harness

Goal-backward check against the phase goal: *a reusable harness that MEASURES
hot-path speed against committed baselines AND PROVES outputs unchanged, with
zero behavior change.*

## Requirement coverage

| Req | Delivered | Evidence |
|-----|-----------|----------|
| BENCH-01 | Benchmark suites + frozen corpus + committed baselines | `tests/benchmarks/test_bench_{db,refresh,builder,api}.py`; `.benchmarks/0001_…`; `pytest -m benchmark --run-bench` → 11 passed |
| BENCH-02 | Regression gate (mean:10%) | `--benchmark-compare=0001 --benchmark-compare-fail=mean:10%` → EXIT 0; documented in README |
| BENCH-03 | Golden equivalence (refresh bytes/readback, build matrix, API JSON, CLI text) | `tests/benchmarks/test_golden_*.py` + `golden/*`; `pytest -m golden --run-bench` → 10 passed |
| BENCH-04 | Profiling entrypoints | `profile_refresh.py` + `profile_builder.py` run sudo-free; py-spy documented (README) |

## must_haves

- ✅ Measurement half: benchmarks for db/refresh/builder/api with committed ro-HEAD baseline.
- ✅ Equivalence half: golden over the frozen corpus (not the mutable live DB); REGEN_GOLDEN to regenerate.
- ✅ Regression gate runnable + green vs baseline.
- ✅ Profiling entrypoints runnable sudo-free; py-spy macOS caveat documented.
- ✅ **Zero behavior change:** `git diff fc26/` is empty. Default `pytest -q` → 341 passed (unchanged from baseline), benchmark/golden/live all gated behind `--run-bench`/`--run-live`.

## Notes / carry-forward
- Frozen corpus covers 12 of 15 formation positions (CF/LWB/RWB have no usable cards in the source DB); builder tests use 4-2-3-1/4-3-3/4-4-2.
- Refresh benchmark/golden target the deterministic write path (the O(n²) upsert Phase 2 fixes); network fetch stages (Phase 4) are excluded by design.
- Env caveat: `FORCE_COLOR` breaks Rich-rendered CLI assertions — run with `NO_COLOR=1`; the new CLI golden forces no-color internally and is env-portable.
- `test_bench_bulk_upsert` is variance-prone — re-baseline after a real Phase 2 win.

**Verdict: PASSED** — harness exists, both halves work, zero behavior change.
