# Plan 01-01 Summary — Foundation

**Status:** Complete · **Requirements:** BENCH-01 (infra)

## What was built
- `pyproject.toml`: added `pytest-benchmark>=5,<6` + `py-spy>=0.4` to `[dev]`; registered `benchmark` and `golden` markers. Runtime deps untouched.
- `tests/conftest.py`: added `--run-bench` opt-in mirroring `--run-live`; benchmark/golden marked tests are skipped unless `--run-bench` is passed.
- `tests/benchmarks/corpus.py`: `load_corpus_repo`, `offline_fetch`, `golden_check` / `golden_check_text` / `golden_check_bytes` (REGEN_GOLDEN=1 regenerates).
- `tests/benchmarks/conftest.py`: `tmp_repo` / `corpus_cards` fixtures.
- `tests/benchmarks/golden/corpus.json`: frozen 40-card corpus (17 leagues, 20 nations), all priced + fully statted, covering 12 of 15 formation positions. Generated deterministically from the real DB once, then committed (decoupled from the mutable live DB).

## Verification
- `pytest -q` → 341 passed, 5 skipped (unchanged from baseline). Benchmark/golden collect nothing by default.
- All 40 corpus cards load as valid `Card`s; all priced + 6 face stats present.
- Zero `fc26/` runtime changes.

## Notes
- CF / LWB / RWB have no usable cards in the real DB — builder benchmarks/golden use formations that don't need them (4-2-3-1, 4-3-3, 4-4-2 are fully covered with swap headroom).
- **Env caveat:** this session sets `FORCE_COLOR=3`, which makes Rich emit ANSI codes and breaks 5 CLI tests' plain-text assertions. Run tests with `NO_COLOR=1` (these tests are green on a normal terminal). CLI golden (Plan 03) forces no-color internally for portability.
