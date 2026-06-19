---
phase: 3
slug: api-responsiveness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-19
---

# Phase 3 — Validation Strategy

> Phase 3 changes handler threading (`app.py`), memoizes leaf functions (`models.py`, `aliases.py`), hoists `find_upgrades` invariants (`upgrade.py`), and caches `/api/meta`. `compute_chemistry`'s algorithm is untouched. The Phase 1 golden (builder_matrix + api_build/upgrade/meta) is the byte-identical gate; the benchmark proves the speedup.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8 (+ pytest-benchmark from Phase 1) |
| **Config** | `pyproject.toml`; `tests/conftest.py` (--run-bench) |
| **Quick run** | `FORCE_COLOR= NO_COLOR=1 pytest -q` |
| **Equivalence gate** | `FORCE_COLOR= NO_COLOR=1 pytest -m golden --run-bench` |
| **Speed gate** | `FORCE_COLOR= NO_COLOR=1 pytest -m benchmark --run-bench --benchmark-storage=.benchmarks --benchmark-compare=0002 --benchmark-compare-fail=mean:10%` |
| **Env note** | `FORCE_COLOR=3` is set in this shell → ALWAYS prefix `FORCE_COLOR= NO_COLOR=1` or 5 CLI tests show spurious ANSI failures |

---

## Sampling Rate

- **Per task commit:** `FORCE_COLOR= NO_COLOR=1 pytest -q` + `pytest -m golden --run-bench` (byte-identical gate).
- **Per wave:** add benchmark suite; confirm /api/build, /api/upgrade, find_upgrades, /api/meta faster, nothing regressed past +10%.
- **Before verify:** golden green, all tests green, benchmark re-baselined (0003) + committed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-offload | 01 | 1 | API-01 | — | N/A | unit | `FORCE_COLOR= NO_COLOR=1 pytest tests/test_api.py -q` | ✅ test_api + ❌ W0 perf test | ⬜ pending |
| 3-memoize | 01 | 1 | API-02 (leaves) | — | N/A | unit | `pytest tests/test_api_perf.py -k memoiz` | ❌ W0 | ⬜ pending |
| 3-meta-cache | 01 | 1 | API-03 | — | N/A | unit+golden | `pytest tests/test_api_perf.py -k meta`; golden api_meta | ❌ W0 | ⬜ pending |
| 3-hoist | 02 | 2 | API-02 (hoist) | — | N/A | golden+bench | `pytest -m golden --run-bench` byte-identical; benchmark faster | ✅ golden (builder_matrix/api) | ⬜ pending |
| 3-regress | all | all | (all) | — | N/A | regression | `FORCE_COLOR= NO_COLOR=1 pytest -q` (0 failures) + golden | ✅ existing + Phase 1 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api_perf.py` — (1) `/api/meta` cache: identical dict across calls + reload after the DB file changes; (2) `slugify`/`canonical_*` expose `cache_info()` (memoized); (3) best-effort concurrency smoke (a long POST doesn't serialize a concurrent GET).
- [ ] No new golden fixtures needed — Phase 1 `builder_matrix.json` + `api_build/upgrade/meta.json` already gate the find_upgrades hoist. Regenerate ONLY if an intended output change occurs (there must be none).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Event loop stays responsive under real concurrent load | API-01 | true parallelism is timing-dependent | Optional: `fc26 serve` + fire a slow `/api/build` and a `/api/cards` concurrently; the GET returns promptly. (Structurally covered by sync def / run_in_threadpool.) |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers MISSING references
- [ ] No watch-mode flags
- [ ] Golden byte-identical gate passes after every change
- [ ] `nyquist_compliant: true` set once tasks map cleanly

**Approval:** pending
