---
phase: 4
slug: async-scraper-rewrite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-19
---

# Phase 4 — Validation Strategy

> Phase 4 adds an async fetch core (`web_async.py`) and async ingest siblings (`enrich`/`expand`/`images`/`refresh`) alongside the unchanged sync functions, then wires them into the CLI (`asyncio.run`) and FastAPI (`to_thread(asyncio.run)`). The hard contract: **byte-identical `data/players.json`, identical result tuples, identical progress sequence, identical CLI/API text**. The Phase 1 golden (refresh_players + readback) plus a NEW fixtured sync-vs-async diff are the byte-identical gate; a NEW simulated-latency benchmark proves the concurrency win (the offline write bench can't — it excludes network).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8 (+ pytest-benchmark from Phase 1) |
| **Async driver** | **NO pytest-asyncio installed** — coroutines run via `asyncio.run(...)` inside plain sync test functions. No `@pytest.mark.asyncio`, no new dep. |
| **Config** | `pyproject.toml` (`markers = live/benchmark/golden`); `tests/conftest.py` (`--run-bench`, `--run-live`) |
| **Quick run** | `FORCE_COLOR= NO_COLOR=1 pytest -q` |
| **Equivalence gate** | `FORCE_COLOR= NO_COLOR=1 pytest -m golden --run-bench` **AND** `FORCE_COLOR= NO_COLOR=1 pytest tests/test_ingest_async.py -q` |
| **Speed gate** | `FORCE_COLOR= NO_COLOR=1 pytest -m benchmark --run-bench --benchmark-storage=.benchmarks --benchmark-compare=0003 --benchmark-compare-fail=mean:10%` |
| **Env note** | `FORCE_COLOR=3` is set in this shell → ALWAYS prefix `FORCE_COLOR= NO_COLOR=1` or 5 CLI tests show spurious ANSI failures |

---

## Sampling Rate

- **Per task commit:** `FORCE_COLOR= NO_COLOR=1 pytest -q` (existing ingest tests stay green) + the new async unit/equivalence test for that task.
- **Per wave:** Wave 2 adds the full `tests/test_ingest_async.py` sync-vs-async diff; Wave 3 adds golden + benchmark.
- **Before verify:** golden green (`-m golden --run-bench` byte-identical), `tests/test_ingest_async.py` green, all tests green, simulated-latency bench shows async ≪ sequential, benchmark re-baselined `0004` + committed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-fetcher | 01 | 1 | SCRAPE-01, SCRAPE-02 | politeness preserved | per-host rate + semaphore + jitter | unit | `FORCE_COLOR= NO_COLOR=1 pytest tests/test_web_async.py -q` | ❌ W0 | ⬜ pending |
| 4-retry | 01 | 1 | SCRAPE-03 | retry parity | 1 retry on any HTTPError; FetchError wording identical | unit | `pytest tests/test_web_async.py -k retry` | ❌ W0 | ⬜ pending |
| 4-enrich-async | 02 | 2 | SCRAPE-03, SCRAPE-04 | single writer; club cache serial | gather fetch / serial upsert in card order | equivalence | `pytest tests/test_ingest_async.py -k enrich` | ❌ W0 | ⬜ pending |
| 4-images-async | 02 | 2 | SCRAPE-03, SCRAPE-04 | single writer | serial upsert in card order | equivalence | `pytest tests/test_ingest_async.py -k images` | ❌ W0 | ⬜ pending |
| 4-expand-async | 02 | 2 | SCRAPE-04 | expand id-suffix order | sequential pagination preserved | equivalence | `pytest tests/test_ingest_async.py -k expand` | ❌ W0 | ⬜ pending |
| 4-refresh-async | 02 | 2 | SCRAPE-04 | merge order | batched single writer | equivalence | `pytest tests/test_ingest_async.py -k refresh` | ❌ W0 | ⬜ pending |
| 4-wire | 03 | 3 | SCRAPE-01, SCRAPE-04 | no nested loop | CLI asyncio.run / API to_thread(asyncio.run) | golden + integration | `pytest -m golden --run-bench`; `pytest tests/test_cli.py tests/test_api.py -q` | ✅ golden/cli/api | ⬜ pending |
| 4-speed | 03 | 3 | SCRAPE-01 | — | N/A | benchmark | simulated-latency bench: async ≪ sequential; compare vs 0003 | ✅ test_bench_refresh (extend) | ⬜ pending |
| 4-regress | all | all | (all) | — | N/A | regression | `FORCE_COLOR= NO_COLOR=1 pytest -q` (0 failures) + golden | ✅ existing + Phase 1 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web_async.py` — AsyncFetcher unit tests (via `asyncio.run`): (1) per-host min-interval enforced across two requests to the same host; (2) two different hosts overlap (cross-host not serialized); (3) jitter applied (next-allowed > now + min_interval is possible; min_interval is a floor); (4) semaphore cap never exceeded — instrument a stub client that records the peak concurrent in-flight count; (5) 1 retry on any `httpx.HTTPError` (a stub raising 500 once → retried → success; raising twice → `FetchError`); (6) `FetchError` message equals `f"could not fetch {url}: {last_error}"`; (7) client built with the right UA + Limits.
- [ ] `tests/test_ingest_async.py` — fixtured sync-vs-async equivalence (via `asyncio.run`): for enrich, expand, images, and full refresh, run sync and async over identical fixtures + tmp corpus repos and assert result tuples EQUAL, `players.json` bytes IDENTICAL, `on_progress` sequence EQUAL. Includes an error-isolation case (one card/page fails → recorded as a miss, batch continues, identical in both).
- [ ] `offline_fetch_async(mapping)` helper (async analog of `corpus.offline_fetch`) + a `_StubFetcher` exposing `async def fetch(url)` — added to `tests/benchmarks/corpus.py` or the test module.
- [ ] No new golden fixture for the write path — Phase 1 `refresh_players.json` + `refresh_readback.json` + the new fixtured diff cover it. Regenerate golden ONLY if an intended output change occurs (there must be none).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real per-host throttling against live sites | SCRAPE-02 | hits the network; rate is timing-dependent | Optional `--run-live`: `fc26 expand --min-ovr 90 --max-pages 2` and confirm ~1 req/s per host in logs. Structurally covered by HostRateLimiter unit tests. |
| End-to-end faster refresh on real network | SCRAPE-01 | network-dependent wall-clock | Optional: time `fc26 refresh --limit N` before/after on a real run; covered deterministically by the simulated-latency bench. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers MISSING references (test_web_async, test_ingest_async, offline_fetch_async)
- [ ] No watch-mode flags
- [ ] Byte-identical gate (golden + test_ingest_async) passes after every change
- [ ] Simulated-latency bench proves async ≪ sequential; benchmark gate no regression vs 0003
- [ ] `nyquist_compliant: true` set once tasks map cleanly

**Approval:** pending
