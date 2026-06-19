# 04-02 SUMMARY — Async ingest variants + byte-identical gate

**Status:** ✅ complete · **Wave:** 2 · **Requirements:** SCRAPE-03, SCRAPE-04

## What was built (async siblings ALONGSIDE the unchanged sync functions)
- `enrich_cards_async` (`enrich.py`) + `_discover_via_club_async`: serial pre-pass resolves every player URL incl. lazy club discovery in `find_all()` order (shared `club_urls`/`club_pages` built single-threaded — risk #3) → `asyncio.gather` player-page fetches with per-card error isolation (`(card, fresh|None, exc|None)`, never raises) → serial upsert in card order with abort-ratio + id-mismatch WARNING (verbatim) + `on_progress` emitted only from the serial consumer (risks #1, #4, #5).
- `upgrade_card_images_async` (`images.py`): gather detail-page fetches → serial `_apply`/upsert in card order, matching the deterministic `workers=1` output (not `as_completed`).
- `expand_cards_async` (`expand.py`): kept SEQUENTIAL (data-dependent pagination + `_resolve` id-suffix order — risk #2 HIGH); only routes each page fetch through the fetcher.
- `refresh_data_async` (`refresh.py`): `async with AsyncFetcher(...)` wrapping `with repo.batch():` → `expand_cards_async` then `enrich_cards_async`; identical banner `on_progress`. Manifest write factored into a shared `_write_manifest` helper (sync + async call it — byte-identical behavior, sync path unchanged in effect).
- `offline_fetch_async` + `async_fetcher_class` helpers in `tests/benchmarks/corpus.py` (async analogs of `offline_fetch`).

## The byte-identical gate
- `tests/test_ingest_async.py` (5 tests, all green): for enrich / enrich-error-isolation / expand-with-id-collision / images / full-refresh, runs sync vs async over identical stubbed fixtures into two tmp repos and asserts **result tuple == · players.json bytes == · on_progress sequence ==**.

## Decisions / deviations
- **Images ordering (intentional):** async always emits `workers=1` (card-order) output, which differs from the sync `workers>1` `as_completed` order. Safe — `test_images.py:179-193` asserts `set()` membership, not sequence; no test pins `workers>1` order.
- **enrich abort counter:** the serial consumer counts `attempts` over the resolved/fetched set (1..len(todo)), matching the sync `failures/attempts` progression at each step.
- No new runtime dependency; all async tests via `asyncio.run`.

## Verification
- `pytest tests/test_ingest_async.py tests/test_enrich.py tests/test_expand.py tests/test_images.py tests/test_refresh.py -q` → 42 passed.
- Full suite: **364 passed, 28 skipped** (was 352 baseline; +7 web_async +5 ingest_async).
