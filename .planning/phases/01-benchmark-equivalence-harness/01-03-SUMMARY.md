# Plan 01-03 Summary — Golden Equivalence + Profiling

**Status:** Complete · **Requirements:** BENCH-03, BENCH-04

## What was built
- `tests/benchmarks/test_golden_refresh.py` — write-path byte equivalence (`refresh_players.json`) + structural readback digest. The zero-behavior-change contract Phase 2 must keep.
- `tests/benchmarks/test_golden_builder.py` — build/upgrade equivalence over a 3 formations × 2 objectives × 3 budgets matrix (`builder_matrix.json`).
- `tests/benchmarks/test_golden_api.py` — `/api/cards`, `/api/meta`, `/api/build`, `/api/upgrade` JSON golden.
- `tests/benchmarks/test_golden_cli.py` — `list`/`show` `--json` stdout golden; forces `NO_COLOR` + uses `--json` so fixtures are portable regardless of `FORCE_COLOR`.
- Committed golden fixtures under `tests/benchmarks/golden/` (api_*.json, builder_matrix.json, refresh_*, cli_*.json).
- `tests/benchmarks/profile_refresh.py` + `profile_builder.py` — cProfile entrypoints, sudo-free.
- `tests/benchmarks/README.md` — Profiling section (cProfile default; py-spy manual w/ macOS sudo + SIP caveat).

## Verification
- `pytest -m golden --run-bench` → 10 passed. Assert run in the **dirty env** (FORCE_COLOR still set) still passed → fixtures portable.
- `pytest tests/benchmarks/ --run-bench` → 21 passed, 1 skipped (live).
- `pytest -q` → 341 passed, 27 skipped (unchanged).
- cProfile scripts run sudo-free and attribute time correctly: refresh → `upsert`/`_save`/`asdict` (Phase 2 target); builder → `find_upgrades`/`_squad_state`/`compute_chemistry` (Phase 3 target).
- Zero `fc26/` changes.

## Notes
- `REGEN_GOLDEN=1` intentionally regenerates fixtures; without it the tests assert equality.
- Golden binds to the frozen corpus, never the mutable live DB.
