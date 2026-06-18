---
phase: 2
slug: data-layer-cache
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 2 — Validation Strategy

> Phase 2 modifies `fc26/db.py` (cache + batched writes) and applies `batch()` at ingest call sites. The Phase 1 harness is the safety net: byte-identical golden + the existing db/expand/enrich/images contract must stay green, and benchmarks must show the speedup with no regression.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8 (+ pytest-benchmark from Phase 1) |
| **Config file** | `pyproject.toml`; `tests/conftest.py` (--run-bench gate from Phase 1) |
| **Quick run command** | `NO_COLOR=1 pytest -q` |
| **Equivalence gate** | `NO_COLOR=1 pytest -m golden --run-bench` |
| **Speed gate** | `NO_COLOR=1 pytest -m benchmark --run-bench --benchmark-storage=.benchmarks --benchmark-compare=0001 --benchmark-compare-fail=mean:10%` |
| **Estimated runtime** | quick ~7s; golden ~2s; benchmark ~10s |

---

## Sampling Rate

- **After every task commit:** `NO_COLOR=1 pytest -q` (db/expand/enrich/images contract must stay green) + `NO_COLOR=1 pytest -m golden --run-bench` (byte-identical gate).
- **After every wave:** add the benchmark suite; confirm find_by_id/refresh faster and nothing regressed past +10%.
- **Before verify:** golden green (byte-identical), all existing tests green, benchmark re-baselined and committed.
- **Max feedback latency:** seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-cache | 01 | 1 | DATA-01, DATA-04 | — | N/A | unit+bench | `NO_COLOR=1 pytest tests/test_db_cache.py tests/test_db.py -q` | ❌ W0 (`tests/test_db_cache.py`) | ⬜ pending |
| 2-invalidate | 01 | 1 | DATA-02 | — | N/A | unit | `NO_COLOR=1 pytest tests/test_db_cache.py -k invalidat` | ❌ W0 | ⬜ pending |
| 2-write | 01 | 1 | DATA-03 (mechanism) | T-2-01 (durability) | fsync on flush | unit | `NO_COLOR=1 pytest tests/test_db_cache.py -k "batch or fsync"` | ❌ W0 | ⬜ pending |
| 2-apply | 02 | 2 | DATA-03 (realized) | — | N/A | bench+golden | refresh benchmark faster; `pytest -m golden --run-bench` byte-identical | ❌ W0 | ⬜ pending |
| 2-regress | all | all | (all) | — | N/A | regression | `NO_COLOR=1 pytest -q` (0 failures) + golden | ✅ existing + Phase 1 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db_cache.py` — 5 cache tests (invalidation, no-redundant-reload/one-write-per-batch, snapshot stability, concurrency smoke, fsync called).
- [ ] `CardRepository._reset_cache()` hook + autouse fixture (only if process-global cache causes cross-test bleed).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CLI-writes-while-server-runs reload | DATA-02 | needs two live processes | Run `fc26 serve`; in another shell `fc26 refresh`; confirm `/api/cards` reflects new pool (covered structurally by the mtime/size invalidation unit test) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Byte-identical golden gate passes after every change
- [ ] `nyquist_compliant: true` set once tasks map cleanly

**Approval:** pending
