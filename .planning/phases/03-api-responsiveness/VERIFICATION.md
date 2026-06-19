---
phase: 3
slug: api-responsiveness
status: passed
verified: 2026-06-19
---

# Phase 3 Verification — API Responsiveness

Goal-backward: *API responsive under concurrency + per-request cost drops — blocking compute off the loop, memoized leaves + hoisted hot loops, cached /api/meta — all byte-identical. compute_chemistry untouched.*

## Requirement coverage

| Req | Delivered | Evidence |
|-----|-----------|----------|
| API-01 | Heavy CPU POSTs (build/upgrade/chem/boost + put_squad) run off the event loop via `run_in_threadpool` | `app.py` async shell + worker; `test_api_perf.py::test_heavy_post_handlers_offload_to_threadpool` |
| API-02 | `lru_cache` on slugify/canonical_*; `find_upgrades` hoists eligible buckets + meta table + per-round name list | `models.py`/`aliases.py` memoized; `upgrade.py` hoisted; find_upgrades 7.74ms→3.90ms, api_build 45.8ms→23.0ms |
| API-03 | `/api/meta` cached on mtime (per resolved path), busted on refresh, byte-identical | `app.py` `_META_CACHE`; `test_api_perf.py` meta cache + versions-no-filter tests |

## must_haves
- ✅ Heavy POSTs off the event loop (concurrent requests don't serialize behind a build).
- ✅ Leaves memoized → compute_chemistry/_same_player faster with NO algorithm change.
- ✅ find_upgrades hoisted; candidate order + `_same_player` prefix + tie-break preserved.
- ✅ `/api/meta` cached + invalidated; versions unfiltered, leagues/nations/clubs filter falsy.
- ✅ **Zero behavior change:** `pytest -m golden --run-bench` byte-identical (builder_matrix, api_build, api_upgrade, api_meta, cli, refresh); `pytest -q` 352 passed; `fc26/chem/engine.py` untouched.

## Speed outcome (0002 → 0003)
`/api/build` ~1.99×, `find_upgrades` ~1.98×, `/api/upgrade` ~1.77× faster; `/api/meta` + `/api/cards` slightly faster; nothing regressed (benchmark gate exit 0).

## Deviation (documented)
Plan said sync-`def` GET handlers. Execution measured that, post-Phase-2 caching, the threadpool thread-hop **regressed** cheap GETs (`/api/meta` +27%, `/api/cards` +14%). Corrected: GETs kept `async def` (cache-fast inline); only heavy POSTs offload. API-01 intent (heavy compute off the loop) fully met. See `03-02-SUMMARY.md`.

## Carry-forward
- Tier-2 (true incremental chemistry, admissible pruning) intentionally deferred to CHEM v2 — not needed to hit Phase 3's goal; the ~2× build/upgrade win came from memoize + hoist alone.

**Verdict: PASSED** — responsiveness + ~2× build/upgrade speedup delivered, output byte-identical.
