# Plan 03-02 Summary — Hoist find_upgrades + Deviation on GET offload

**Status:** Complete · **Requirements:** API-02 (hoist)

## What was built
- **`fc26/builder/upgrade.py` `find_upgrades` hoisted** (order + prefix + tie-break preserved):
  - Precompute once: per-position `eligible[position]` buckets (priced + position-eligible, in **original pool order**) and a `(card_id, position) → meta_score` table. The inner loop iterates the bucket (not the full 2,434-card pool every round) and reads meta_score from the table.
  - Per slot: hoist the "other XI player names" list out of the candidate loop; the prefix-aware `_same_player` check is kept verbatim.
  - `compute_chemistry` / `_squad_state` unchanged. Candidate iteration order preserved so the `delta==best and cost<net_cost` tie-break resolves identically.

## Deviation from plan (documented)
The plan (and BACKEND-COMPUTE.md) said to convert GET read handlers to sync `def` for the threadpool. **Execution measurement reversed that decision:** after Phase 2's pool cache, GET reads are cache-served (cheap), so the sync-`def` threadpool **thread-hop added latency** — the benchmark gate caught `/api/meta` +27% and `/api/cards` +14% regressions. The research's sync-GET recommendation assumed pre-cache read cost, which no longer holds.

**Correction (in this plan's scope since it touches the same gate):** GET handlers reverted to `async def` (cache-fast, inline — no hop); only the CPU-heavy POSTs (`build`/`upgrade`/`chem`/`boost`) + `put_squad` keep the `run_in_threadpool` offload (where event-loop blocking actually mattered). API-01's intent — heavy compute off the event loop — is fully met by the POST offload. `tests/test_api_perf.py` updated accordingly (`test_heavy_post_handlers_offload_to_threadpool`).

## Verification
- `pytest -q` → 352 passed, 28 skipped.
- `pytest -m golden --run-bench` → 10 passed (**byte-identical**: builder_matrix, api_build, api_upgrade, api_meta — the hoist changed nothing observable).
- Benchmark gate vs `0002` (`--benchmark-compare-fail=mean:10%`) → **EXIT 0, no regression**.

## Before → After (mean, Phase 2 `0002` → Phase 3 `0003`)
| Path | 0002 | 0003 | Change |
|------|------|------|--------|
| `/api/build` | 45.8 ms | 23.0 ms | **~1.99× faster** |
| `find_upgrades` | 7.74 ms | 3.90 ms | **~1.98× faster** |
| `/api/upgrade` | 8.56 ms | 4.84 ms | **~1.77× faster** |
| `/api/meta` | 664 µs | 614 µs | slightly faster (cache, no hop) |
| `/api/cards` | 1195 µs | 1162 µs | slightly faster |

New baseline `0003` committed (Phase 4 compares against it).

## Notes
- The ~2× build/upgrade win comes from memoized `slugify`/`canonical_*` (03-01) + the loop hoist (03-02), with `compute_chemistry`'s algorithm untouched. Tier-2 (true incremental chemistry) remains deferred as CHEM v2 — not needed to hit this phase's goal.
