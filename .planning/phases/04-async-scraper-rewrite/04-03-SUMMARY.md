# 04-03 SUMMARY — Wire CLI + FastAPI + prove

**Status:** ✅ complete · **Wave:** 3 · **Requirements:** SCRAPE-01, SCRAPE-04

## What was built
- **CLI** (`cli.py`): `refresh`/`enrich`/`expand`/`images` now drive the async pipeline via `asyncio.run(...)` inside the existing `with repo.batch():`. `refresh` calls `refresh_data_async` directly (it batches internally). `enrich`/`expand`/`images` build an `AsyncFetcher(concurrency=4, min_interval=1.0)` in a local async helper. `--workers` maps to the fetcher's `concurrency`. Output text, error handling (`except FC26Error: _fail`), and exit codes unchanged.
- **FastAPI** (`app.py` `_refresh_loop`): `await asyncio.to_thread(lambda: asyncio.run(refresh_data_async(...)))` — fresh loop in a worker thread, never nested in uvicorn's loop; keeps the whole scrape + upsert file I/O off the server loop. `_META_CACHE` bust + CancelledError handling unchanged. Dropped the now-unused `fetch_html`/`jittered_sleep`/`refresh_data` imports.
- **Simulated-latency benchmark** (`tests/benchmarks/test_bench_refresh.py`): `_LatencyFetcher` (each fetch `await asyncio.sleep(5ms)`); `test_bench_async_enrich_beats_sequential` runs `enrich_cards_async` over 24 cards (batched so write cost doesn't mask the fetch win) and asserts mean wall-clock < 0.4 × the analytic sequential baseline `(N+1)*LAT`. Measured ≈13ms vs 125ms sequential → ~10× (proves concurrency deterministically, offline).

## Test updates (mechanism only — behavior contract preserved)
- `tests/test_cli.py`: the 8 enrich/expand command stubs now patch the `_async` ingest names with `async def` stubs (the CLI now `await`s them). All exit-code + summary-text assertions unchanged.

## Verification
- Full suite: **364 passed, 29 skipped** (`FORCE_COLOR= NO_COLOR=1 pytest -q`).
- Golden byte-identical gate: **10 passed** (`pytest -m golden --run-bench`) — players.json + readback + api/builder/cli all unchanged.
- Simulated-latency bench: async ≈13ms ≪ 50ms threshold (sequential 125ms).
- Benchmark baseline re-saved as **0004**.

## Benchmark regression gate — noise finding (reported faithfully)
`--benchmark-compare=0003 --benchmark-compare-fail=mean:10%` flagged `test_bench_bulk_upsert`, `test_bench_bulk_upsert_batched` (and once `build_squad`) as >10% slower than 0003. These are **environmental noise, not a code regression**:
- The readings were unstable run-to-run (`bulk_upsert` +14% then +29%); a real regression is stable.
- All flagged benches exercise the **write path (`db.py`)** and **builder**, which Phase 4 did **not** touch — `git diff 046b21c -- fc26/db.py fc26/builder fc26/chem` is empty. Phase 4 changed only `api/app.py`, `cli.py`, and the 5 ingest files.
- This is a shared background-job machine; the I/O-bound upsert benches are load-sensitive (matches the Phase 2 note that these benches are noisy).
- The hard constraint (golden byte-identical) and the async-speedup bench both passed.

No path that Phase 4 modified regressed. 0004 is the new reference for Phase 5.
