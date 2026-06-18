# Async Scraping Research — footie ingest rewrite

**Researched:** 2026-06-17
**Dimension:** Async scraping (perf milestone, brownfield)
**Decision already made:** rewrite `fc26/ingest` from sequential module-level `httpx.get` to async `httpx.AsyncClient` + bounded concurrency, connection reuse, politeness preserved, **byte-identical output**.
**Overall confidence:** HIGH on the httpx/asyncio API and the integration shape; MEDIUM on the exact concurrency/rate numbers (tuning knobs, not correctness — must be measured against the new benchmark harness).

---

## Version verification (not training memory)

| Component | Declared (`pyproject.toml`) | Installed in `.venv` | Notes |
|-----------|------------------------------|----------------------|-------|
| Python | `requires-python >=3.12` | **3.14.5** | All patterns below (`asyncio.run`, `asyncio.to_thread`, `asyncio.Semaphore`, `asyncio.TaskGroup`) are stable in 3.12+. `TaskGroup` (3.11+) is available; safe to use. |
| httpx | `>=0.27` | **0.28.1** | API verified by live introspection of the installed package (below). |
| selectolax | `>=0.3` | present | CPU-bound HTML parsing (`HTMLParser`), used in `images.py`, `futbin.py`, `futgg.py`, `fcratings_player.py`. |
| fastapi / uvicorn | `>=0.111` / `>=0.30` | present | Already runs the refresh loop via `asyncio.to_thread` (`app.py:89`). |

**httpx 0.28.1 API confirmed by `inspect` against the installed wheel (HIGH confidence — not docs, the actual code):**

```text
httpx.Limits(*, max_connections=None, max_keepalive_connections=None, keepalive_expiry=5.0)
AsyncClient default limits = Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=5.0)
AsyncClient default timeout = Timeout(timeout=5.0)
httpx.Timeout(timeout, *, connect=, read=, write=, pool=)        # granular per-phase timeouts
httpx.AsyncHTTPTransport(..., retries=N)                         # retries param EXISTS
```

> Important caveat verified against httpx docs: `AsyncHTTPTransport(retries=N)` retries **only `ConnectError`/`ConnectTimeout`** — *not* read errors, 5xx, or 429. The current `fetch_html` retries on **any** `httpx.HTTPError` (`web.py:24`). To stay output-equivalent on the error path we must replicate the broader "1 retry on any HTTPError" in our own wrapper, not lean on the transport's `retries`.

---

## Summary

The current ingest is dominated by **wall-clock sleep**, not CPU or bandwidth: every fetch is a fresh TCP+TLS connection (`web.py:18`, no shared `Client`) followed by a deliberate `sleep(1.0..2.0)` (`enrich.py:51,84,119,126`, `expand.py:54`, `images.py:235,248`, jitter `refresh.py:29-32`). A full refresh touches ~2,400 cards × ~1.5 s/card ≈ tens of minutes, almost all of it sleeping serially.

The win is to **fetch concurrently within a per-host politeness budget** while keeping exactly one writer to `data/players.json`. The code is already shaped for this in two ways that de-risk the rewrite:

1. **`fetch_html` is injected** everywhere (`Callable[[str], str]` param on `enrich_cards`, `expand_cards`, `upgrade_card_images`, `refresh_data`, plus `sbc.py`/`objectives.py`). The sleep is injected too. This is the seam — we can swap implementations without touching parse logic.
2. **`images.py` already proves the safe concurrency contract** (`images.py:230-268`): fetch+parse in a `ThreadPoolExecutor`, but **every `repo.upsert` runs on the single consuming thread** because each upsert rewrites the whole file (`db.py:85-93`). Concurrent writers would clobber. The async design must mirror this: **concurrent fetch/parse, serial upsert.**

Recommended approach: a shared `httpx.AsyncClient` (pool reuse) + an `asyncio.Semaphore` (hard concurrency cap) + a per-host **min-interval rate limiter** (preserves the politeness contract that the `sleep(1.0)` currently provides) + a manual retry/backoff/jitter wrapper that reproduces the existing 1-retry semantics. Bridge to the **sync Typer CLI via `asyncio.run`** (CLI commands are plain sync functions using `time.sleep` — no running loop, so `asyncio.run` is clean) and to the **FastAPI auto-refresh via the existing `asyncio.to_thread` boundary**, running `asyncio.run(pipeline())` *inside* that worker thread (its own loop, never nested in the server loop). selectolax parsing stays on a worker thread (`asyncio.to_thread`) only if it measurably blocks the gather; per-page parse is small, so this is optional and should be benchmarked before adding.

---

## Recommended async architecture (code shapes mapped to this repo)

### 1. New async fetch core — replaces `web.py`

A single long-lived `AsyncClient` per pipeline run, bounded by `Limits`, plus a polite throttle and retry wrapper. The async equivalent of `fetch_html`.

```python
# fc26/ingest/web_async.py  (new)
from __future__ import annotations
import asyncio, random, time, httpx
from collections import defaultdict
from urllib.parse import urlsplit
from ..errors import FetchError

USER_AGENT = "footie-playbook/0.1 (personal squad tool)"

# Pool: cap total + keepalive so connections are REUSED per host (fixes 1.3).
_LIMITS = httpx.Limits(max_connections=8, max_keepalive_connections=8, keepalive_expiry=30.0)
# Granular timeouts — current code uses a flat 15s; keep read generous, add a
# pool timeout so a saturated pool surfaces fast instead of hanging.
_TIMEOUT = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)


class HostRateLimiter:
    """Per-host minimum interval between request STARTS (min-interval token bucket
    of size 1). Reproduces the politeness of the old sequential sleep(1.0), but
    measured per host so fut.gg / fcratings / futbin throttle independently."""
    def __init__(self, min_interval: float) -> None:
        self._min = min_interval
        self._next: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def wait(self, host: str) -> None:
        async with self._locks[host]:          # serialize the gate per host
            now = time.monotonic()
            delay = self._next[host] - now
            if delay > 0:
                await asyncio.sleep(delay)
            # jitter (0..min) preserves refresh.jittered_sleep behaviour
            self._next[host] = time.monotonic() + self._min + random.uniform(0, self._min)


class AsyncFetcher:
    def __init__(self, *, concurrency: int = 4, min_interval: float = 1.0,
                 retries: int = 1) -> None:
        self._sem = asyncio.Semaphore(concurrency)      # hard cap on in-flight
        self._rl = HostRateLimiter(min_interval)
        self._retries = retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncFetcher":
        self._client = httpx.AsyncClient(
            limits=_LIMITS, timeout=_TIMEOUT, follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def fetch(self, url: str) -> str:
        host = urlsplit(url).netloc
        last: Exception | None = None
        # match web.py: 1 retry on ANY httpx.HTTPError (NOT transport retries=,
        # which only covers ConnectError) -> output-equivalent error behaviour.
        for _ in range(self._retries + 1):
            await self._rl.wait(host)            # politeness gate (per host)
            async with self._sem:                # concurrency cap (global)
                try:
                    resp = await self._client.get(url)
                    resp.raise_for_status()
                    return resp.text
                except httpx.HTTPError as exc:
                    last = exc
                    # exponential backoff + jitter ONLY on retry (old code retried
                    # immediately; small backoff is strictly politer, still <= old
                    # total time. Keep it modest so behaviour stays equivalent.)
                    await asyncio.sleep(random.uniform(0.0, 0.5))
        raise FetchError(f"could not fetch {url}: {last}")
```

Notes:
- `Semaphore` caps *simultaneity*; `HostRateLimiter` caps *rate*. You need **both** — a semaphore alone lets N requests fire the instant slots free up (bursts), which is what gets IPs blocked. (Confirmed across multiple scraping guides; see Sources.)
- Sizing: hosts are only **three** (`fut.gg`, `fcratings.com`, `futbin.com` — verified by grepping all URL literals in `fc26/ingest/`). A global `concurrency=4` with `min_interval=1.0` per host keeps each host at ~1 req/s (same as today) while three hosts can overlap. This is the single biggest lever; **make `concurrency` and `min_interval` parameters and tune against the benchmark harness**, do not hard-code aggressive values.

### 2. Concurrent fetch / serial upsert — the enrich + images loops

These iterate over a **known list of cards** (`repo.find_all()`), so the fetch set is knowable up front and fully parallelizable. Pattern (drop-in for `enrich_cards` body and the `workers>1` branch of `upgrade_card_images`):

```python
async def _run(fetcher, cards, parse, repo, on_progress):
    async def work(card):
        try:
            html = await fetcher.fetch(url_for(card))
            return card, parse(html), None          # parse() = selectolax, CPU
        except FC26Error as exc:
            return card, None, exc                   # ERROR ISOLATION: never raises out

    # bounded by the fetcher's own semaphore; gather keeps INPUT ORDER.
    results = await asyncio.gather(*(work(c) for c in cards))

    for card, parsed, exc in results:               # SINGLE WRITER, in card order
        if exc is not None:
            missed.append(f"{card.id}: {exc}")
            continue
        repo.upsert(apply(card, parsed))             # serial — one file writer
        on_progress(f"... {card.id}")
```

Key properties:
- **Error isolation**: each `work()` returns its exception instead of raising, so one bad card never aborts the batch. `asyncio.gather(..., return_exceptions=True)` is an alternative, but the explicit tuple is clearer and avoids re-raising surprises. (Do **not** use a bare `TaskGroup` here — a TaskGroup cancels siblings on first exception, which would change behaviour vs. today's per-card try/except.)
- **Serial upsert in card order** preserves the single-writer invariant (`db.py` whole-file rewrite) and keeps the abort-ratio counters (`attempts`/`failures`, `ABORT_CHECK_AFTER`, `ABORT_FAILURE_RATIO`) deterministic.
- **selectolax stays in `work()`** (on the event loop) by default. Per-page parse is small (one card's table). Only if profiling shows it stalls the gather, wrap it: `parsed = await asyncio.to_thread(parse, html)`. Flag this as a tuning decision, not a default — adding `to_thread` per page has overhead and can be net-negative at this scale.

### 3. `expand_cards` is special — pagination is data-dependent (do NOT fully parallelize)

`expand.py:46-79` is a `while True` that fetches page N, and only knows whether page N+1 exists *after* parsing N (`if not cards: break`, `if len(cards) < ROWS_PER_FULL_PAGE: break`). Furthermore `_resolve` (`expand.py:82-95`) calls `repo.find_by_id` and depends on **previously upserted cards being visible** to suffix id collisions. So:

- **Cannot** gather all pages — you don't know the page count, and `_resolve`/upsert must see prior pages.
- **Can** prefetch a small look-ahead window (e.g. fetch pages N..N+3 concurrently, then process them in order, stop when a short/empty page appears, discarding over-fetched pages). This bounds extra requests to `< concurrency` and keeps `_resolve` order-correct because upserts still run sequentially in page order.
- Lower-risk alternative for v1: keep `expand` sequential (it's typically a small number of pages above min_ovr 84) and only async-ify `enrich` + `images`, which are the 2,000+-card loops that dominate. **Recommend shipping enrich+images async first, expand look-ahead second** (sequencing below).

### 4. Pipeline entry points

```python
# fc26/ingest/refresh.py  — async variant alongside the sync one
async def refresh_data_async(repo, *, min_ovr, concurrency, min_interval,
                             on_progress, enrich_limit=None, manifest_path=None):
    async with AsyncFetcher(concurrency=concurrency, min_interval=min_interval) as f:
        expand = await expand_cards_async(repo, min_ovr=min_ovr, fetcher=f, ...)
        enrich = await enrich_cards_async(repo, fetcher=f, limit=enrich_limit, ...)
    # manifest write unchanged (sync file I/O)
    return RefreshResult(expand=expand, enrich=enrich)
```

---

## Politeness / rate-limiting (the contract that must NOT regress)

Today's politeness = **strictly 1 request at a time per process, ≥1 s (often 1–2 s with jitter) between requests, across all hosts combined.** That is *over*-polite (it serializes unrelated hosts). The async target keeps the *per-host* guarantee while allowing cross-host overlap:

| Mechanism | Today | Async target | Why it stays polite |
|-----------|-------|--------------|---------------------|
| Concurrency cap | implicit = 1 | `asyncio.Semaphore(N)`, N small (start 4) | Hard ceiling on in-flight requests; never a burst storm. |
| Per-host rate | global `sleep(1.0)` | `HostRateLimiter(min_interval=1.0)` keyed by netloc | Each of the 3 hosts still sees ~1 req/s; hosts no longer block each other. |
| Jitter | `jittered_sleep` 0–100% extra (`refresh.py:29-32`) | `+ random.uniform(0, min_interval)` in the limiter | Same anti-metronome property preserved. |
| Connection reuse | none (new TCP/TLS each call) | shared `AsyncClient` + keepalive | Fewer handshakes = *less* load on the host, strictly politer. |
| Backoff on failure | immediate retry | exp backoff + jitter on retry | Politer than today under errors. |
| User-Agent | `footie-playbook/0.1 …` | identical | Keep the honest UA. |

**Hard rule for the roadmap:** expose `concurrency` and `min_interval` (and per-host overrides if needed) as parameters with conservative defaults; never let a refresh exceed roughly the current per-host request rate without an explicit, measured decision. The benchmark harness (PROJECT.md active item) is the gate for raising them.

> `sbc.py` and `objectives.py` have their *own* `default_fetch_html` with a **browser UA** and raise `httpx.HTTPError` (not `FetchError`) — see `sbc.py:86-101`, `objectives.py:55-70`. If they're brought into the async fetcher, preserve their distinct UA and exception type, or leave them on the sync path for v1 (they're small hub crawls, not the 2,400-card hot loop).

---

## CLI (sync) + API (async loop) integration — both addressed

### CLI — clean `asyncio.run`

The Typer commands (`enrich`, `expand`, `images`, `refresh` in `cli.py:183-306`) are **plain synchronous functions** that pass `sleep=time.sleep`. There is **no running event loop**, so `asyncio.run(...)` is the correct, idiomatic bridge — none of the "event loop already running" problems apply here.

```python
@app.command()
def refresh(min_ovr=..., limit=..., db=DB_OPTION) -> None:
    repo = CardRepository(db)
    result = asyncio.run(refresh_data_async(          # <- the only new line of plumbing
        repo, min_ovr=min_ovr, concurrency=4, min_interval=1.0,
        on_progress=console.print, enrich_limit=limit,
        manifest_path=db.parent / "last_refresh.json",
    ))
    console.print(f"refresh done: {result.expand.new} new, ...")  # unchanged output
```

`on_progress=console.print` still works — progress callbacks are invoked from the serial upsert loop (the consuming coroutine), not from inside gathered tasks, so output ordering stays deterministic (by card id) and rich stays happy.

### FastAPI — keep the existing `to_thread` boundary; run `asyncio.run` inside the thread

`app.py:75-101` already runs the blocking refresh in a worker thread: `await asyncio.to_thread(refresh_data, repo, fetch_html=fetch_html, sleep=jittered_sleep, ...)`. The **lowest-risk** integration keeps that boundary and simply runs the async pipeline *inside* the worker thread, which has **no event loop of its own**, so `asyncio.run` creates a fresh loop there — never nested in uvicorn's server loop:

```python
# app.py _refresh_loop — replace the to_thread(refresh_data, ...) call:
result = await asyncio.to_thread(
    lambda: asyncio.run(refresh_data_async(
        repo, min_ovr=min_ovr, concurrency=4, min_interval=1.0,
        manifest_path=db_path.parent / "last_refresh.json",
    ))
)
```

Why not run the pipeline directly on uvicorn's loop (no thread)? It would also work and avoid a thread, **but** the serial `repo.upsert` calls do blocking file I/O (whole-file read+write of 4.4 MB) — those belong off the request-serving loop. Keeping the `to_thread` wrapper means the entire scrape (including the upsert file I/O) stays off the event loop, exactly as today, so request latency during a refresh is unaffected. This is the conservative, behavior-preserving choice. (Once the in-memory cache / batched-write items from PROJECT.md land, this can be revisited.)

`asyncio.CancelledError` handling in `_refresh_loop` (`app.py:98-99`) still works: cancelling the outer task cancels the `to_thread` await; the inner `asyncio.run` loop completes or is abandoned with the thread. No `nest_asyncio` needed anywhere — avoid it.

---

## Output-equivalence risks (must be guarded — these are the dangerous bits)

The milestone constraint is **byte-identical `data/players.json` + identical CLI/API text**. Concurrency introduces ordering hazards. Ranked by risk:

1. **Concurrent upsert would corrupt data — CRITICAL.** `db.upsert` is read-modify-write over the whole file with `merge_cards` (`db.py:85-93`); two simultaneous upserts = lost update (last writer wins, merge of the other lost). **Guard:** exactly one writer. Fetch/parse concurrently, `upsert` serially on the consuming coroutine — identical to the proven `images.py:188-192` single-writer rule. The on-disk file is *sorted by id* in `_save` (`db.py:99`), so final file order is independent of upsert order — but the *merge result* is not, so serialization is still mandatory.

2. **`expand._resolve` id-suffix collision logic depends on upsert order — HIGH.** `_resolve` (`expand.py:82-95`) suffixes a special card's id with its ovr when the base id already exists with a different ovr, using `repo.find_by_id` to detect the prior. If two cards that collide are processed out of order or in parallel, the suffix decision changes → different ids in the DB. **Guard:** within `expand`, keep cards processed in the **same page order** and upserted **sequentially** (look-ahead may prefetch pages but must process/upsert them in order). Add a test that scrapes a fixture with a known collision and asserts identical ids vs. the sequential baseline.

3. **`enrich` abort-ratio + dedupe counters — MED.** `enriched/skipped/missed`, `attempts`, `failures`, and the `ABORT_FAILURE_RATIO` early-abort (`enrich.py:99-102`) are order-sensitive *as reported*. With gather, decide counter semantics: count over the *whole batch* after completion (cleaner) vs. mid-stream. The `club_pages` / `club_urls` lazy cache (`enrich.py:52-53,117-126`) is a shared dict mutated during discovery — under concurrency it must be either prefetched once before the gather or guarded; **recommend resolving all player URLs (incl. club discovery) first, then gathering the player-page fetches**, so the shared cache is built single-threaded. **Guard:** snapshot the `EnrichResult` tuples and diff against a sequential run on a fixture.

4. **Progress/log text ordering — MED (cosmetic but tested?).** If any test asserts the *sequence* of `on_progress` lines, emitting them from the serial post-gather loop (in card/page order) keeps them deterministic. Emitting from inside gathered tasks would interleave nondeterministically. **Guard:** always call `on_progress` from the serial consumer, never from a gathered task.

5. **`merge_cards` field-precedence under reordering — MED.** If the same card id appears twice in one batch (e.g. base + special variants), the *order* they merge can change which fields win. Today they merge in iteration order; preserve that iteration order in the serial upsert loop. **Guard:** golden-file diff of `players.json` before/after on a fixture refresh.

6. **Retry/error semantics drift — LOW/MED.** Old `fetch_html` retries once on **any** `httpx.HTTPError`; httpx transport `retries=` only covers connect errors. Use the manual wrapper (above) to keep "1 retry on any HTTPError". The added backoff sleep is strictly politer and only on the retry path, but if a test asserts exact failure messages, keep `FetchError(f"could not fetch {url}: {last_error}")` wording identical (`web.py:26`).

**Recommended universal guard:** the PROJECT.md benchmark/golden harness should run a *fixtured* refresh (no network) through both the sequential and async pipelines and assert (a) `players.json` bytes identical after sorting, (b) `EnrichResult`/`ExpandResult`/`ImagesResult` tuples equal, (c) progress-line sequence equal. Build this **before** flipping the default to async.

---

## Suggested sequencing for the roadmap

1. **Benchmark + golden harness first** (already a PROJECT.md item) — fixtured sequential-vs-async equivalence diff. Nothing async ships without it.
2. **Async fetch core** (`web_async.py`: `AsyncFetcher`, `HostRateLimiter`) + unit tests for the limiter (per-host interval, jitter, semaphore cap) and retry equivalence.
3. **Async `enrich` + `images`** (the 2,000+-card loops — biggest win, simplest: known card list, gather + serial upsert). Resolve club discovery before gather (risk #3).
4. **Async `expand`** with bounded page look-ahead (risk #2); or defer and keep sequential if page counts are small.
5. **Wire CLI** (`asyncio.run`) and **FastAPI** (`to_thread(asyncio.run(...))`) — flip defaults only after the harness is green.
6. **Optional:** `sbc`/`objectives` onto the async fetcher (preserve their distinct UA + exception type), and `selectolax` → `to_thread` *only if* profiling shows event-loop stalls.

---

## Confidence levels

| Claim | Confidence | Basis |
|-------|-----------|-------|
| httpx 0.28.1 `Limits`/`AsyncClient`/`Timeout`/`AsyncHTTPTransport(retries=)` signatures & defaults | HIGH | Live `inspect` of installed wheel + official docs (resource-limits, transports). |
| Transport `retries=` covers only ConnectError/ConnectTimeout (need manual retry for HTTPError parity) | HIGH | httpx transports docs + exceptions docs. |
| Semaphore = concurrency, token-bucket/min-interval = rate; need both | HIGH | Multiple current scraping guides converge; matches existing `sleep`-based design intent. |
| CLI `asyncio.run` is safe (no running loop in Typer sync commands) | HIGH | Read `cli.py` — commands are sync, use `time.sleep`. |
| `to_thread(asyncio.run(...))` for FastAPI keeps scrape off the server loop & avoids nesting | HIGH | Read `app.py:75-101`; worker thread has no loop. |
| Single-writer upsert is mandatory under concurrency | HIGH | Read `db.py:85-101` (whole-file RMW) + existing `images.py` comment documenting exactly this. |
| `expand._resolve` ordering is an equivalence risk | HIGH | Read `expand.py:82-95` — `find_by_id`-dependent id suffixing. |
| Exact `concurrency`/`min_interval` values (4 / 1.0s) | MEDIUM | Conservative starting point matching today's per-host rate; must be tuned vs. benchmark, not asserted. |
| selectolax needs `to_thread` | LOW | Per-page parse is small; only profiling can justify it. Default = leave on loop. |

## Sources

- [HTTPX — Resource Limits](https://www.python-httpx.org/advanced/resource-limits/) (max_connections / max_keepalive_connections / keepalive_expiry defaults)
- [HTTPX — Transports](https://www.python-httpx.org/advanced/transports/) (`AsyncHTTPTransport(retries=)` covers connect errors only)
- [HTTPX — Exceptions](https://www.python-httpx.org/exceptions/)
- [HTTPX — Async Support](https://www.python-httpx.org/async/)
- [Scrapfly — How to Rate Limit Async Requests in Python](https://scrapfly.io/blog/posts/how-to-rate-limit-asynchronous-python-requests) (semaphore vs rate, token bucket)
- [ProxiesAPI — Effective Strategies for Rate Limiting Async Requests in Python](https://proxiesapi.com/articles/effective-strategies-for-rate-limiting-asynchronous-requests-in-python)
- [StudyRaid — Handling rate limits and polite scraping (asyncio)](https://app.studyraid.com/en/read/15007/518827/handling-rate-limits-and-polite-scraping)
- [The Web Scraping Club — Rate limiting with exponential backoff](https://substack.thewebscraping.club/p/rate-limit-scraping-exponential-backoff)
- [bobbyhadz — RuntimeError: This event loop is already running](https://bobbyhadz.com/blog/runtime-error-this-event-loop-is-already-running) (why `asyncio.run` is fine from sync but not nested)
- [Python docs — asyncio event loop / to_thread](https://docs.python.org/3/library/asyncio-eventloop.html)
- Local verification: `inspect.signature` of `httpx` 0.28.1 in `.venv` (Python 3.14.5); repo reads of `fc26/ingest/{web,enrich,expand,refresh,images}.py`, `fc26/api/app.py`, `fc26/db.py`, `fc26/cli.py`.
