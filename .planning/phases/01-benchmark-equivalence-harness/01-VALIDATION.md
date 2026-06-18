---
phase: 1
slug: benchmark-equivalence-harness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 1 is purely additive (zero `fc26/` runtime changes); the harness it builds becomes the validation contract for Phases 2-5.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8 (+ pytest-benchmark >=5,<6 to be added; py-spy for profiling) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (markers); `tests/conftest.py` (skip logic, mirror `live`) |
| **Quick run command** | `pytest -q` (default: fast, offline, benchmark+golden skipped) |
| **Full suite command** | `pytest --run-live` + `pytest -m "benchmark or golden" --run-bench` |
| **Estimated runtime** | quick ~ unchanged from today; bench/golden opt-in only |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q` (fast offline floor must stay green) + `pytest -m golden --run-bench` for the golden being built.
- **After every plan wave:** Run `pytest -m "benchmark or golden" --run-bench` (full Phase 1 suite) + `pytest --run-live` if a live path was touched.
- **Before `/gsd:verify-work`:** `ro` HEAD baselines committed in `.benchmarks/`; golden fixtures committed; default `pytest` runtime confirmed unchanged; all existing tests green.
- **Max feedback latency:** quick run seconds; bench/golden seconds-to-low-minutes (opt-in).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-W0 | 01 | 0 | (infra) | T-1-01 (dep legitimacy) | dev deps verified on PyPI before install | setup | `pip install -e ".[dev]"` | ❌ W0 | ⬜ pending |
| 1-bench | 01 | 1 | BENCH-01 | — | N/A | benchmark | `pytest -m benchmark --run-bench --benchmark-autosave` | ❌ W0 | ⬜ pending |
| 1-gate | 01 | 1 | BENCH-02 | — | N/A | benchmark/gate | `pytest -m benchmark --run-bench --benchmark-compare --benchmark-compare-fail=mean:10%` | ❌ W0 | ⬜ pending |
| 1-golden | 02 | 1 | BENCH-03 | T-1-02 (no secrets in fixtures) | golden corpus = public FUT data only | golden/equivalence | `pytest -m golden --run-bench` | ❌ W0 | ⬜ pending |
| 1-profile | 02 | 1 | BENCH-04 | T-1-03 (sudo py-spy is manual only) | cProfile default, sudo never in automated run | docs + smoke | `python tests/benchmarks/profile_refresh.py` | ❌ W0 | ⬜ pending |
| 1-regress | all | all | (all) | — | N/A | regression | `pytest -q` (0 failures, runtime unchanged) | ✅ ~346 existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — add `pytest-benchmark>=5,<6` + `py-spy` to `[dev]`; register `benchmark`/`golden` markers
- [ ] `tests/conftest.py` — add `--run-bench` + skip logic for `benchmark`/`golden` (mirror `live`/`--run-live`)
- [ ] `tests/benchmarks/conftest.py` + `corpus.py` — deterministic corpus fixtures, offline fetch helper, golden helpers (`golden_check` / `golden_check_text` with `REGEN_GOLDEN`)
- [ ] `tests/benchmarks/golden/corpus.json` — committed frozen card pool (~30-60 cards covering all formation positions across ≥2 leagues/nations)
- [ ] `pip install -e ".[dev]"` after pyproject edit

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| py-spy live sampling of refresh | BENCH-04 | macOS requires `sudo`; not part of automated run | Follow `tests/benchmarks/README.md` py-spy section (Homebrew interpreter, SIP-exempt) |
| Dev-dependency legitimacy | (infra) | slopcheck unavailable; supply-chain check | Verify `pytest-benchmark`/`py-spy` on PyPI (done; re-confirm before install) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency acceptable (quick run unchanged; bench/golden opt-in)
- [ ] `nyquist_compliant: true` set in frontmatter (set by planner once tasks map cleanly)

**Approval:** pending
