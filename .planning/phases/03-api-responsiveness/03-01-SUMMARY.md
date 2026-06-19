# Plan 03-01 Summary — Offload + Memoize + /api/meta Cache

**Status:** Complete · **Requirements:** API-01, API-02 (leaves), API-03

## What was built
- **API-02 (memoize):** `@lru_cache(maxsize=None)` on `slugify` (`models.py`) and `canonical_league`/`canonical_nation`/`canonical_club` (`aliases.py`). Pure str→str maps; auto-speeds `compute_chemistry`, `_same_player`, `make_card_id` with NO algorithm change.
- **API-01 (offload):** GET read endpoints (`list_cards`, `get_card`, `list_squads`, `get_squad`, `get_meta`, `get_objectives`, `get_sbcs`, `get_updates`, `get_value`) → plain `def` (Starlette runs them in the anyio threadpool). POST/PUT (`put_squad`, `post_chem`, `post_boost`, `post_upgrade`, `post_build`) keep an `async def` shell that `await request.json()` then runs the blocking body via `await run_in_threadpool(_worker)`. Error flow (FC26Error → handler) preserved.
- **API-03 (/api/meta cache):** module-level `_META_CACHE: dict[Path, (mtime_ns, dict)]` + `_META_LOCK`, keyed on `db_path.resolve()`; self-invalidates on file mtime change; explicitly cleared in the auto-refresh loop. Byte-identical predicates preserved (versions unfiltered; leagues/nations/clubs filter falsy).
- `tests/test_api_perf.py` — 4 tests: meta cache identical + invalidates on mtime; versions-no-filter contract; leaf functions memoized; GET handlers sync / POST handlers async.

## Verification
- `pytest -q` → 352 passed, 28 skipped (was 348 + 4 new).
- `pytest -m golden --run-bench` → 10 passed (**byte-identical**: api_meta, api_build, api_upgrade, builder_matrix, cli, refresh).
- `fc26/chem/engine.py` unchanged (compute_chemistry algorithm untouched — Tier-2 deferred).
- Side effect: the full suite dropped ~6.6s → ~4s (memoized slugify/canonical_*).

## Notes
- POSTs use the thin-async-shell + `run_in_threadpool` form (not Pydantic models) to keep existing body-parsing/error messages byte-identical.
- `/api/meta` cache keyed per resolved path so concurrent tests with distinct tmp DBs don't collide.
