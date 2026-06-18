# Backend / API Compute Performance Research

**Project:** footie (FC 26 FUT squad assistant)
**Dimension:** Backend / API compute (FastAPI, single uvicorn process)
**Researched:** 2026-06-17
**Overall confidence:** HIGH (claims grounded in the actual source + official docs)

> Aligns with `.planning/codebase/CONCERNS.md` items 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 and the
> PROJECT.md milestone constraints (in-memory cache, no new infra, byte-identical output, tests
> green). This file adds the *prescriptive* layer those docs deliberately omit: exact fixes by
> file:line, the GIL/threadpool distinction, and an equivalence harness for the risky changes.

---

## Summary

The API is a single-process, CPU-bound FastAPI app over a **2,434-card** pool stored as a
**4.4 MB JSON file** (`data/players.json`). Every request constructs a fresh
`CardRepository(db_path)` and calls `find_all()`, which **re-reads and re-parses the entire
4.4 MB JSON and rebuilds 2,434 frozen `Card` dataclasses from scratch** (`fc26/db.py:48-60`).
That alone is a large fixed cost on every endpoint, paid even by trivial calls like `/api/meta`.

On top of that, two endpoints do heavy pure compute **inside `async def` handlers**, which runs
on the event loop and **serializes all concurrent requests** behind the slow one:

- `/api/build` (`fc26/api/app.py:292-325`) → `build_squad` → `find_upgrades(max_swaps=11)`
- `/api/upgrade` (`fc26/api/app.py:278-290`) → `find_upgrades(max_swaps=3)`

`find_upgrades` (`fc26/builder/upgrade.py:103-161`) is a nested loop: `max_swaps` rounds ×
~11 slots × ~2,434 candidates, and for **each surviving candidate** it builds a trial XI and
calls `compute_chemistry` (`fc26/chem/engine.py:78`), which rebuilds three `Counter`s and
re-canonicalizes every name (`canonical_club`/`canonical_league`/`canonical_nation`, each a
fresh `slugify` + regex) on all 11 players. Order of magnitude:

- `/api/build`: ~11 × 11 × 2,434 ≈ **295K `compute_chemistry` calls** (each ~11 cards ⇒ low
  millions of `slugify`/canonical calls), plus an O(11) `_same_player` check **per candidate**
  that calls `slugify` twice each (`fc26/builder/upgrade.py:120-124`, `:52-64`).
- `/api/upgrade`: ~3 × 11 × 2,434 ≈ **80K `compute_chemistry` calls**.

The wins split cleanly into two tiers:

1. **Safe mechanical wins** (provably output-identical): get blocking/CPU work off the event
   loop, cache the card pool, memoize the pure `slugify`/`canonical_*` functions, and hoist
   invariant work out of the hot loops. These cannot change output if done as described.
2. **Algorithmic wins** (need equivalence testing): incremental chemistry deltas per swap, and
   candidate-set pruning. These can change output if the equivalence is subtly wrong, so they
   require an explicit before/after equivalence harness.

**Critical GIL fact for this milestone:** the deployment is standard CPython 3.14 (the repo
runs 3.14.5; `requires-python >=3.12`). The default build still has the GIL. Free-threaded
`python3.14t` exists and is now "officially supported," **but it is not the default and silently
re-enables the GIL if any C extension hasn't opted in** — so do not assume parallel threads.
Therefore: a threadpool offload (sync `def` or `run_in_threadpool`/`asyncio.to_thread`) **frees
the event loop so other requests stay responsive, but does NOT make a single build/upgrade
request faster** under the GIL. Single-request latency only improves via memoization +
algorithmic + pool-caching work.

---

## Event-loop / threadpool strategy

### The bug today
Handlers are `async def` but call **synchronous, blocking, CPU-heavy** code directly:

| Handler | File:line | Blocking call inside async def |
|---|---|---|
| `/api/build` | `app.py:292-325` | `repo.find_all()`, `build_squad(...)`, `compute_chemistry(...)` |
| `/api/upgrade` | `app.py:278-290` | `repo.find_all()`, `find_upgrades(...)` |
| `/api/meta` | `app.py:327-342` | `repo.find_all()` + set comprehensions |
| `/api/cards` | `app.py:157-216` | `repo.find_all()`/`search()`, filter+sort |
| `/api/value` | `app.py:414-459` | `repo.find_all()`, filtering, `value_picks`, `_squad_positions` N+1 |
| `/api/objectives` | `app.py:344-368` | `find_all()`, file read |
| `/api/chem`, `/api/boost` | `app.py:255-276` | `find_all()` (via `resolve_cards`), `compute_chemistry` |

While any one of these runs, the **event loop is blocked**: every other in-flight request waits.
A single `/api/build` (potentially seconds) stalls the whole server. (The auto-refresh loop is
already correct — it uses `asyncio.to_thread`, `app.py:89`.)

### What to do (two equivalent mechanical options)

**Option A — convert handlers to sync `def` (recommended, simplest).**
FastAPI/Starlette automatically runs a plain `def` path operation in a worker thread via
`anyio.to_thread.run_sync`, so the event loop stays free. This is the idiomatic fix for an
endpoint whose body is entirely blocking/CPU work with no `await` inside.
- Change `async def post_build`/`post_upgrade`/`get_meta`/`list_cards`/`get_value`/`get_card`/
  `list_squads`/`get_squad`/`get_objectives`/`get_sbcs`/`get_updates` to `def`.
- **Caveat:** sync handlers can't `await request.json()`. The POST handlers currently read the
  body with `await request.json()` (`app.py:249,257,266,279,293`). To go sync, switch to a
  **Pydantic body model** (FastAPI parses the JSON before calling the sync function) or keep a
  thin `async def` shell that reads the body then calls a sync worker via `run_in_threadpool`.
  The Pydantic-model route is cleaner and also gives free request validation — but note it would
  add a 422 schema where today malformed bodies flow into `lineup_from_dict`/`parse_budget`;
  to keep output byte-identical, prefer the thin-async-shell + `run_in_threadpool` form for the
  POSTs so the existing error messages/paths are unchanged.

**Option B — keep `async def`, offload the blocking call.**
Wrap the blocking work in `await run_in_threadpool(fn, ...)` (Starlette) or
`await asyncio.to_thread(fn, ...)`. Lower-churn, lets you keep `await request.json()` and the
exact existing validation/error flow.

```python
from starlette.concurrency import run_in_threadpool

@app.post("/api/build")
async def post_build(request: Request) -> dict:
    body = await request.json()
    return await run_in_threadpool(_build_impl, body)   # _build_impl is pure-sync
```

Both options give the same correctness (the pure functions are unchanged) and the same outcome:
**event loop is freed**. Recommended split: **Option A** for the GET read endpoints (no body),
**Option B** for the POSTs (`/api/build`, `/api/upgrade`, `/api/chem`, `/api/boost`, `/api/squads`
PUT) to preserve existing body-parsing/error behavior exactly.

### Thread-pool sizing
Starlette's anyio threadpool defaults to **40 worker threads**, shared process-wide. For a
home/single-user tool that's plenty. If many `/api/build`s could pile up you can raise it in the
lifespan (`limiter = anyio.to_thread.current_default_thread_limiter(); limiter.total_tokens = N`),
but for this app the default is fine — and remember each extra concurrent CPU build still
contends on the GIL, so more threads ≠ more throughput for CPU work.

### When threadpool helps vs GIL limits (the honest version)
- **I/O-bound** (file reads of `players.json`/squad JSON, the scrape in the refresh loop):
  threadpool genuinely helps — the GIL is released during blocking I/O, so other requests run.
- **CPU-bound Python** (`find_upgrades`, `compute_chemistry`, `slugify`): under the default
  GIL build, the threadpool **only** keeps the event loop responsive to *other* requests; it
  does **not** speed up or parallelize the heavy request itself. Two simultaneous `/api/build`s
  will not run twice as fast on the standard interpreter.
- **Do not reach for `multiprocessing`/`ProcessPoolExecutor` here** (also ruled out by PROJECT.md
  "no new infra" / in-process constraint): the per-call overhead of pickling the 2,434-card pool
  to a worker process would dwarf the compute, and it complicates a single-process deployment.
  The right lever for single-request latency is memoization + algorithmic improvement (below),
  not parallelism.
- **Free-threaded `python3.14t`** is an option *later* if true parallel builds are ever needed,
  but it is out of scope for a "behavior byte-identical, tests green" milestone and brings C-ext
  compatibility risk. Note it for the roadmap as a future dimension, not this milestone.

**Correctness risk of this section:** essentially none if the offloaded function is the existing
pure function. The one real trap is Option A + `await request.json()` (can't await in sync def)
— handle via the thin-async-shell/`run_in_threadpool` form for POSTs. Threads also must not share
mutable global state; the current functions don't — **but** the pool cache introduced below is
shared mutable state, so its loader must be safe under concurrent threads (see risk note there).

---

## Memoization wins (safe — provably equivalent)

All of these target **pure, deterministic, side-effect-free** functions. Memoizing a pure
function cannot change output.

### 1. Cache the card pool — the single biggest fixed win (CONCERNS 3.1)
Every request does `CardRepository(db_path).find_all()` (`db.py:48-60`): read 4.4 MB, JSON
parse, build 2,434 `Card` dataclasses (with nested `FaceStats`/`SubStats`). This happens on
*every* endpoint, including `/api/meta`, and **multiple times per request** in places
(`/api/upgrade` calls `find_all()` for `resolve_cards` *and* again at `app.py:288`;
`resolve_cards` itself calls `find_all()` at `lineup.py:114`; `find_by_id` calls `find_all()`
per id at `db.py:62-66`; `_squad_positions` does up to 11 `find_by_id` ⇒ 11 full parses,
`app.py:395-412` / CONCERNS 3.4).

**Fix:** load the pool once and cache it, keyed by the file's mtime so a refresh invalidates it.
`Card` is frozen/immutable so a shared cached tuple is safe to hand to every request.

```python
import threading
_pool_lock = threading.Lock()
_pool_cache: tuple[int, tuple[Card, ...], dict[str, Card]] | None = None

def cached_pool(db_path: Path) -> tuple[tuple[Card, ...], dict[str, Card]]:
    global _pool_cache
    mtime = db_path.stat().st_mtime_ns
    with _pool_lock:
        if _pool_cache is None or _pool_cache[0] != mtime:
            pool = CardRepository(db_path).find_all()
            _pool_cache = (mtime, pool, {c.id: c for c in pool})
        return _pool_cache[1], _pool_cache[2]
```

The `threading.Lock` matters because once handlers run in the anyio threadpool, multiple threads
can hit the loader concurrently. Build `by_id` once (cached above) so `resolve_cards`/`find_by_id`
become dict lookups. The auto-refresh writes via atomic `os.replace` (`db.py:104-114`), which
bumps mtime, so the cache self-invalidates on refresh.
**Correctness risk:** none, provided invalidation is keyed on mtime (or you explicitly bust the
cache at the end of `refresh_data`). The only subtlety: `find_all()` raises `DatabaseError` on a
bad schema — preserve that by letting the cache loader raise (don't cache the exception).

### 2. Memoize `slugify` and the `canonical_*` helpers (CONCERNS 3.6)
These are the hottest leaf functions in the search. `slugify` (`models.py:98-100`) does
`unicodedata.normalize` + encode/decode + regex on every call; `canonical_club`/`_league`/
`_nation` (`aliases.py:59-76`) each call `slugify` then a dict lookup. In a `/api/build` they
are invoked low-millions of times, almost always on the **same finite vocabulary** of player
names, clubs, leagues, nations (≤ a few thousand distinct strings).

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def slugify(text: str) -> str: ...

@lru_cache(maxsize=None)
def canonical_club(name: str) -> str: ...
# same for canonical_league, canonical_nation
```

`maxsize=None` is safe because the input domain is bounded by the DB vocabulary.
**Correctness risk:** none — these are pure string→string maps with no hidden state. The only
thing to confirm is they're always called with `str` (they are; call sites pass `card.club`
etc. only when truthy). `make_card_id` (`models.py:103`) and `_same_player` (`upgrade.py:52`)
automatically benefit since they call `slugify`. Note `lru_cache` is thread-safe in CPython.

### 3. Precompute per-card derived attributes once (lookup table instead of recompute)
Better than memoization for the hottest values: compute them **once per pool load** and stash
them, so the hot loop reads an attribute instead of recomputing. Candidates, all currently
recomputed inside the inner loop or inside `compute_chemistry`:

- `canonical_club(card.club)`, `canonical_league(card.league)`, `canonical_nation(card.nation)`
  — recomputed in `engine.py:99,104,113,131,133,135` (twice per card per `compute_chemistry`:
  once when counting, once when scoring).
- `is_icon(card)` / `is_hero(card)` (`rules.py:28-41`) — regex on `card.version`, recomputed in
  `engine.py:93-94 and 126`.
- `slugify(card.player_name)` for `_same_player`.
- `meta_score(card, position)` for each (card, eligible position) — pure (`meta.py:41-48`).

Build a small parallel struct (e.g. a dict `card.id -> CardChemFacts`) at pool-load time. The
hot loop then never re-canonicalizes. **Correctness risk:** none if computed with the exact same
functions and only when the corresponding field is present (mirror the `if card.club:` guards in
`engine.py`).

### 4. Hoist invariant work out of the build/upgrade hot loops
Independent of caching, several values are recomputed inside loops where they're constant:

- **`out_meta`/`outgoing`/`position` per slot:** computed once per slot already
  (`upgrade.py:111-112`) — good. But `meta_score(candidate, position)` (`upgrade.py:129`) is
  recomputed every round for the same candidate/position pairs; precompute a
  `(card_id, position) -> meta_score` table once.
- **The `_same_player` "one real player per XI" check** (`upgrade.py:120-124`) runs an O(11)
  scan calling `slugify` twice per comparison, **for every candidate, every slot, every round**.
  Hoist the set of current player-slugs (excluding the slot under test) to a precomputed
  `frozenset` per round, and compare against `slugify(candidate.player_name)` once. With slugify
  memoized this is cheap; structurally it drops from O(candidates × 11 × slugify) to
  O(candidates × set-lookup). **Watch the prefix semantics:** `_same_player` is not pure slug
  equality — it also matches token-boundary prefixes (`upgrade.py:62-64`), so a plain
  `slug in set` is NOT equivalent. Keep the prefix logic; the safe hoist is precomputing the
  current XI's slugs once per round and still running the prefix check against that small list
  (11 items) instead of re-slugifying both sides each time.
- **Eligible-candidate prefiltering:** the position-eligibility test (`upgrade.py:116`) and
  `price is None` test (`:114`) reject most of the 2,434 pool every round. Precompute, once,
  `eligible_by_position[position] -> tuple[Card,...]` (priced + position-eligible). The inner
  loop then iterates only the ~hundreds eligible for that slot, not the full pool.

**Correctness risk for #4:** low, but **iteration order matters** because of the
`delta == best.score_delta and cost < best.net_cost` tie-break (`upgrade.py:137-139`). Any
prefiltering MUST preserve the original relative order of candidates so ties resolve identically.
Treat order-preserving filters as safe; treat any sort/reorder as an algorithmic change needing
the equivalence harness. The `_same_player`-set hoist must preserve the prefix-match semantics.

---

## Algorithmic speedups (need equivalence verification)

These change *how* the answer is computed and can alter output if the equivalence is imperfect.
Each must ship with the equivalence harness described at the end of this section.

### A1. Incremental chemistry delta instead of full recompute per swap (highest payoff)
Today every trial XI calls `compute_chemistry` from scratch (`upgrade.py:133` →
`engine.py:78`), rebuilding three `Counter`s over all 11 players and re-scoring all 11, just to
evaluate swapping **one** slot. The team differs from the base XI by exactly one card.

**Idea:** compute the base XI's chem state once per round (counts, icon-league bonus, per-player
chem, team total). For a candidate swap in slot S, derive the new `team_total` by removing the
outgoing card's contributions and adding the incoming card's, recomputing only the affected
tiers. Because tier points are **threshold step functions** (`CLUB_TIERS`/`NATION_TIERS`/
`LEAGUE_TIERS` in `rules.py:15-17`), a single swap can shift any player who shares the changed
club/nation/league across a threshold — so the delta is **not** purely local. A correct
incremental form must:
- recompute points for the **affected club key, nation key, league key** (old and new) for *all*
  in-position sharers, not just the swapped slot;
- handle the **icon-league global +1** (`engine.py:90,109,118-119`) — adding/removing an icon
  shifts *every* league's effective count;
- handle **hero 2× league weight** and **icon 2× nation weight** (`engine.py:104,115`);
- handle the **in-position gate** (out-of-position contributes nothing, `engine.py:94-95`);
- handle **pseudo-leagues** (`PSEUDO_LEAGUES`, `engine.py:114,136`) and the icon/hero **flat
  MAX_PLAYER_CHEM** short-circuit (`engine.py:126-127`);
- apply the **per-player `min(chem, MAX_PLAYER_CHEM)` cap** (`engine.py:140`) and **manager
  bonus** (`engine.py:138`).

Given that web of interactions, a **safe partial version** is much lower risk and still a big
win: keep `compute_chemistry`'s algorithm intact but make it cheap via the precomputed per-card
facts (Memoization #3) — that removes the slugify/regex cost without changing the algorithm at
all, so it needs no equivalence harness beyond the existing tests. This is really a memoization
win disguised as an algorithm one, and it is the recommended first move.

**Recommendation for the roadmapper:** treat "make `compute_chemistry` cheap via precomputed
facts" as a **safe** task (Tier 1 #5/#7), and "true incremental single-swap delta" as a
**separate, optional, high-risk** task gated behind the equivalence harness. Do not bundle them.

**Correctness risk:** HIGH for true incremental. The threshold + icon-global-bonus interactions
are exactly where an incremental implementation silently diverges from the full recompute. Only
attempt with the harness below and only if profiling shows `compute_chemistry` is still the
bottleneck after the safe wins.

### A2. Candidate-set reduction / pruning
- **Eligibility pre-bucketing** (described in Memoization #4) is the safe form: same predicates,
  order preserved.
- **Aggressive pruning** (e.g. "skip candidates whose `meta_score` can't beat the current best
  delta", or "only consider top-N by meta per position") **is an algorithmic change** that can
  drop the swap the greedy algorithm would otherwise have picked, because score combines
  `meta + CHEM_WEIGHT*chem` (`upgrade.py:84`, `CHEM_WEIGHT=3.0`) and a low-meta card can still
  win on chem. A naive meta-only prune is **not equivalence-safe**. If pruning is pursued, it
  must be a *provable* bound (an admissible upper bound on achievable delta), not a heuristic
  top-N.
**Correctness risk:** MEDIUM-HIGH for heuristic pruning; LOW for order-preserving pre-bucketing.

### Equivalence-verification plan (mandatory for A1/A2)
Behavior must stay byte-identical (PROJECT.md hard constraint), so before merging any algorithmic
change:

1. **Golden-output capture.** Before changing anything, add a test that runs `/api/build` and
   `/api/upgrade` (and direct `find_upgrades`/`build_squad`) over the **real `players.json`** for
   a matrix of inputs — every formation in `FORMATIONS` (`formations.py:10-23`), both objectives
   (`meta`, `rating`, `meta.py:18`), and several budgets (too-small, tight, generous) — and
   serialize the full result (`asdict(plan)` / `asdict(result)`), capturing it as a golden
   fixture.
2. **Differential test.** After the change, assert the new implementation produces the
   **exact same `UpgradePlan`/`BuildResult`** (every swap, order, deltas, spent, before/after
   scores, warnings) for every matrix entry. Equality must be structural, not just team_total.
3. **`compute_chemistry` parity sweep.** For the incremental delta specifically, generate
   thousands of random single-swap trial XIs and assert
   `incremental_total(base, swap) == compute_chemistry(trial).team_total` for **every** one,
   covering edge cases on purpose: icon in/out, hero in/out, manager match toggling, tier
   boundary crossings (counts at 1↔2, 4↔5, 7↔8 for clubs/nations, 3↔5↔8 for leagues),
   out-of-position swaps, pseudo-league cards, and missing club/league/nation fields.
4. **Property test (if `hypothesis` is acceptable as a dev dep):** for random lineups + random
   swaps, incremental == full. This catches the threshold/icon interactions humans miss.
5. **Keep the existing suite green** as the floor; the differential test is the ceiling.
6. **Tie-break guard.** Add a test that two candidates with identical `score_delta` but different
   `net_cost` resolve to the cheaper one (`upgrade.py:137-139`), and that candidate **order** is
   preserved by any prefilter — this is the most likely silent regression.

---

## /api/meta caching (CONCERNS 3.3)

`/api/meta` (`app.py:327-342`) re-reads the whole pool and recomputes
`leagues/nations/clubs/versions` sorted-unique sets on **every call**, plus serializes the static
`FORMATIONS` and `available_styles()`. `FORMATIONS` and styles are compile-time constants; the
four sorted sets derive purely from the (now cached) pool.

**Fix:** derive meta from the cached pool and cache the result keyed by the same pool mtime/
version used in Memoization #1.

```python
_meta_lock = threading.Lock()
_meta_cache: tuple[int, dict] | None = None

def cached_meta(db_path: Path) -> dict:
    global _meta_cache
    mtime = db_path.stat().st_mtime_ns
    with _meta_lock:
        if _meta_cache is None or _meta_cache[0] != mtime:
            pool, _ = cached_pool(db_path)
            _meta_cache = (mtime, {
                "formations": {n: list(s) for n, s in FORMATIONS.items()},
                "styles": list(available_styles()),
                "leagues": sorted({c.league for c in pool if c.league}),
                "nations": sorted({c.nation for c in pool if c.nation}),
                "clubs":   sorted({c.club for c in pool if c.club}),
                "versions": sorted({c.version for c in pool}),   # NO filter — match original
            })
        return _meta_cache[1]
```

**Invalidation (specified):** the cache key is `db_path.stat().st_mtime_ns`. The auto-refresh
writes the DB atomically via `os.replace` (`db.py:104-114`), which updates mtime, so the next
`/api/meta` recomputes automatically. Belt-and-suspenders: also explicitly clear `_meta_cache`
(and `_pool_cache`) at the end of `refresh_data`/the refresh loop (`app.py:89-97`) so a stale
cache can never be served even on a filesystem with coarse mtime resolution.

**Byte-identical caveat:** the original `get_meta` computes
`versions = sorted({c.version for c in all_cards})` with **no** truthiness filter (versions are
always present per the model). The other three (`leagues`/`nations`/`clubs`) DO filter falsy
(`app.py:331-333`). The snippet above mirrors that exactly: filter the three, do **not** filter
versions. Confirm against the existing `/api/meta` test before/after.

**Correctness risk:** none, given mtime-keyed invalidation + explicit bust on refresh + matching
the original set-comprehension predicates exactly (watch the `versions` no-filter detail).

---

## Risk-ordered list (for the roadmapper)

### Tier 1 — Safe mechanical wins (output-identical; do first)
| # | Change | Files | Risk | Note |
|---|---|---|---|---|
| 1 | Cache card pool keyed on `players.json` mtime; build `by_id` once; stop calling `find_all()` multiple times per request; thread-lock the loader | `db.py:48-66`, `app.py` all handlers, `lineup.py:114`, `app.py:395-412` | None | Biggest fixed win (CONCERNS 3.1/3.4); invalidate on mtime + explicit bust on refresh |
| 2 | `lru_cache` on `slugify`, `canonical_club/league/nation` | `models.py:98`, `aliases.py:59-76` | None | Pure string maps; `maxsize=None` safe (bounded vocab); CONCERNS 3.6 |
| 3 | Get CPU work off the event loop: sync `def` for GETs, `run_in_threadpool` for POSTs | `app.py:255-459` | None | Keeps server responsive (CONCERNS 3.2); does NOT speed a single build under GIL |
| 4 | Cache `/api/meta` keyed on pool mtime + explicit bust on refresh | `app.py:327-342` | None | Match original set predicates exactly (versions: no filter); CONCERNS 3.3 |
| 5 | Precompute per-card chem facts (canonical keys, is_icon/is_hero, slug) once per pool load | `engine.py`, `rules.py`, `db.py` | None | Lookup-table instead of recompute in hot loop |
| 6 | Hoist invariants out of `find_upgrades` loop: eligible-by-position buckets (order-preserving), per-round current-player-slug list (keep prefix semantics), `(card,pos)->meta_score` table | `upgrade.py:103-161`, `build.py` | Low | MUST preserve candidate order (tie-break) and `_same_player` prefix logic |

### Tier 2 — Algorithmic wins (need equivalence harness; do only if profiling still warrants)
| # | Change | Files | Risk | Gate |
|---|---|---|---|---|
| 7 | Make `compute_chemistry` cheaper using precomputed facts / prebuilt counters (same algorithm) | `engine.py:78-160` | Low-Med | Existing tests + chem parity sweep |
| 8 | True incremental single-swap chemistry delta | `engine.py`, `upgrade.py:133` | High | Full equivalence harness (A1 plan) |
| 9 | Provable (admissible) candidate pruning | `upgrade.py:113-153` | High | Differential test; NO heuristic top-N |

### Tier 3 — Out of scope for this milestone (note for future)
| # | Change | Risk | Note |
|---|---|---|---|
| 10 | Free-threaded `python3.14t` for parallel builds | High | C-ext compat; not default; only if true parallelism ever needed |
| 11 | `multiprocessing`/process pool | High | Pickling 2,434-card pool per call dwarfs compute; also barred by "no new infra" |

**Sequencing logic:** Tier 1 #1 (pool cache) and #2 (slugify memoize) likely remove the majority
of wall-clock cost on their own and are zero-risk — do them first and re-profile. #3 (event-loop
offload) is orthogonal correctness/responsiveness and can land anytime. Only proceed to Tier 2
if, after Tier 1, `compute_chemistry`/`find_upgrades` is still the measured bottleneck — and #8
only behind the full equivalence harness, never bundled with the safe wins. **Add a profiling
harness first** (PROJECT.md "Benchmark/profiling harness" requirement) so every claim above is
measured, not assumed.

---

## Confidence levels

| Claim | Confidence | Basis |
|---|---|---|
| Handlers block the event loop (async def + sync CPU/IO) | HIGH | Direct read of `app.py:255-459`; CONCERNS 3.2 |
| `find_all()` re-parses 4.4 MB / 2,434 cards per call, multiple times/request | HIGH | `db.py:48-66`, `lineup.py:114`, `app.py:288,395-412`; measured file size + card count |
| `find_upgrades` ~11×11×2,434 (build) / ~3×11×2,434 (upgrade) compute_chemistry calls | HIGH | `upgrade.py:103-161`, `build.py:19,100-102`, `formations.py` (11 slots), 2,434-card pool |
| `compute_chemistry` rebuilds Counters + re-canonicalizes per call | HIGH | `engine.py:78-160`, `aliases.py:59-76` |
| Sync `def` endpoints auto-offload to anyio threadpool (default 40 threads) | HIGH | Starlette/FastAPI docs (verified) |
| Threadpool/`to_thread` does NOT parallelize CPU-bound Python under default GIL | HIGH | Python docs + multiple sources; standard CPython 3.14 default build |
| Python 3.14 free-threading is supported but not default, re-enables GIL if any C-ext opts out | HIGH | python.org what's-new 3.14 / free-threading howto (verified) |
| `slugify`/`canonical_*` memoization is output-safe | HIGH | Functions are pure string→string (`models.py:98`, `aliases.py:59-76`) |
| `_same_player` is prefix-aware (not pure slug equality) — hoist must preserve it | HIGH | `upgrade.py:52-64` |
| Incremental chemistry must handle thresholds + icon-global-bonus to stay equivalent | HIGH | `rules.py:15-21`, `engine.py:90,104,109,115,118-119,126-140` |
| mtime-keyed cache self-invalidates on refresh | HIGH | atomic `os.replace` in `db.py:104-114` bumps mtime |
| Exact request volume / latency numbers in production | LOW | No profiling data captured; estimates are structural, not measured — run `cProfile`/`py-spy` on a real `/api/build` to confirm bottleneck ranking before Tier 2 |

**Gap / recommended next step:** none of the above is measured — capture a `cProfile` of one
`/api/build` and one `/api/upgrade` against the real `players.json` to rank the bottlenecks and
confirm that Tier 1 (#1/#2) is sufficient before investing in Tier 2 incremental chemistry. This
is exactly the PROJECT.md "Benchmark/profiling harness" Active item.

---

## Sources

- [Python support for free threading — Python 3.14 docs](https://docs.python.org/3/howto/free-threading-python.html) (HIGH)
- [What's new in Python 3.14](https://docs.python.org/3/whatsnew/3.14.html) (HIGH)
- [Thread Pool — Starlette docs](https://starlette.dev/threadpool/) (HIGH)
- [How to limit max threads with sync endpoints — fastapi/fastapi Discussion #8690](https://github.com/fastapi/fastapi/discussions/8690) (MEDIUM)
- [Kludex/fastapi-tips](https://github.com/Kludex/fastapi-tips/blob/main/README.md) (MEDIUM)
- [Python's GIL and Asyncio relationship](https://shanechang.com/p/python-gil-asyncio-relationship/) (MEDIUM)
- Primary source: the footie codebase itself (`fc26/api/app.py`, `fc26/builder/upgrade.py`, `fc26/builder/build.py`, `fc26/chem/engine.py`, `fc26/models.py`, `fc26/chem/aliases.py`, `fc26/db.py`, `fc26/builder/meta.py`, `fc26/chem/rules.py`, `fc26/chem/formations.py`, `fc26/chem/lineup.py`) (HIGH)
- Cross-reference: `.planning/codebase/CONCERNS.md` (items 3.1–3.6) and `.planning/PROJECT.md` (HIGH)
