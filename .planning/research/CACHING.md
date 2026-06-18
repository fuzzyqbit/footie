# Data-Layer Caching Research — footie `CardRepository`

**Domain:** In-process cache + indexed access over a single JSON-file repository
**Researched:** 2026-06-17
**Mode:** Feasibility + prescriptive design (brownfield perf milestone)
**Overall confidence:** HIGH

---

## Summary

The "DB" is one ~4.4 MB JSON file (`data/players.json`, 2,434 cards, schema_version 1).
`fc26/db.py` re-reads and re-parses the **whole** file on every `find_all`/`find_by_id`/`search`,
and `upsert` does `find_all()` + `_save()` (full re-serialize + atomic write) **per card**
(`db.py:85-101`). A refresh upserts ~2,400 cards → ~2,400 full parses + ~2,400 full
re-serializations of a 4.4 MB document = the dominant O(n²) cost the milestone targets.

The decision is locked: **keep the JSON format, add an in-process cache.** That is exactly
the right call at this scale. The whole pool fits trivially in memory (a few MB of dataclasses),
the process is single-node/single-user, and an in-process `dict` indexed by `id` turns every
read into O(1)/O(n-in-RAM) with **zero** disk I/O after the first load.

Two independent wins, both inside `db.py`, with no change to the on-disk bytes or any caller:

1. **Load-once + index-by-id read cache** — parse the file once, hold `tuple[Card,...]` +
   `dict[str, Card]`, serve all reads from RAM. Reload only when the file's `mtime`/`size`
   changes (handles the CLI-writes-then-API-reads and external-edit cases).
2. **Batched + durable writes** — replace the per-`upsert` full rewrite with an in-memory
   dict mutation plus a single deferred `_save()` (a `flush()` / context-manager boundary, or
   a guaranteed flush at end of each ingest stage). Keep the existing temp-then-`os.replace`
   atomicity and **add `fsync`** for durability the current code lacks.

The cache lives **inside `CardRepository`**, keyed by absolute path, shared across the many
per-request `CardRepository(db_path)` constructions (`app.py` builds a fresh repo in ~12
handlers). This is the single most important shape decision: today each handler constructs a
new repo and pays a full parse — the cache must therefore be **process-global keyed by path**,
not per-instance, or the per-request construction defeats it.

---

## Recommended approach (with code shapes)

### Where the cache lives — process-global, path-keyed, behind `CardRepository`

`CardRepository` is constructed fresh per request/per handler (`app.py:186, 220, 259, 269,
285, 300, 329, 355, 432, 433/434, 408`) and once per CLI command (`cli.py:76, 93, 106, 116,
128, 167, 189, 218, 252, 289, 316, 362, 424, 483, 565, 598, 644`). A per-instance cache would
be thrown away every request. So the cache must be keyed by the resolved file path and live at
module scope, with each `CardRepository` instance a thin handle onto the shared entry.

```python
# fc26/db.py — sketch, not final
import threading

class _CacheEntry:
    __slots__ = ("lock", "cards", "by_id", "mtime", "size", "dirty")
    def __init__(self):
        self.lock = threading.RLock()
        self.cards: tuple[Card, ...] | None = None   # snapshot, immutable
        self.by_id: dict[str, Card] = {}             # index into snapshot
        self.mtime: float | None = None
        self.size: int | None = None
        self.dirty: bool = False                     # in-memory writes not yet flushed

_CACHES: dict[Path, _CacheEntry] = {}
_CACHES_LOCK = threading.Lock()

def _entry_for(path: Path) -> _CacheEntry:
    key = path.resolve()
    with _CACHES_LOCK:
        e = _CACHES.get(key)
        if e is None:
            e = _CACHES[key] = _CacheEntry()
        return e
```

### Read path — load-once, reload on mtime/size change

```python
class CardRepository:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._entry = _entry_for(self._path)

    def _ensure_loaded(self) -> None:
        e = self._entry
        with e.lock:
            if e.dirty:
                return                       # in-memory writes are source of truth
            st = self._stat_or_none()        # os.stat; None if file missing
            fresh = (
                e.cards is not None
                and st is not None
                and st.st_mtime == e.mtime
                and st.st_size == e.size
            )
            if fresh:
                return
            cards = self._parse_file()       # the *only* json.loads of the file
            e.cards = cards
            e.by_id = {c.id: c for c in cards}
            if st is not None:
                e.mtime, e.size = st.st_mtime, st.st_size

    def find_all(self) -> tuple[Card, ...]:
        self._ensure_loaded()
        return self._entry.cards or ()       # immutable snapshot — safe to return

    def find_by_id(self, card_id: str) -> Card | None:
        self._ensure_loaded()
        return self._entry.by_id.get(card_id)   # O(1) — was O(n) full scan (db.py:62-66)

    def search(self, text: str) -> tuple[Card, ...]:
        self._ensure_loaded()
        # identical fold/alias logic as db.py:68-81, but over the cached snapshot
```

`find_all` must return the **same immutable `tuple[Card, ...]`** the current code returns
(`db.py:48`), and `card_from_dict` already yields frozen dataclasses, so callers that iterate
(`enrich.py:57`, `app.py` filters) see a stable snapshot. **Do not** return a live view of a
mutable list — `enrich_cards` iterates `repo.find_all()` while calling `repo.upsert` inside the
loop (`enrich.py:57` + `enrich.py:86`); mutating the iterated collection would change behavior
or raise. Snapshot-on-read preserves today's semantics exactly.

### Write path — mutate the index, defer/batch the disk write, keep atomicity, add fsync

`upsert` currently does, per card: `find_all()` (full parse) + dict rebuild + `_save()` (full
serialize + atomic write) (`db.py:85-101`). New shape: mutate the cached `by_id`, rebuild the
snapshot tuple, mark dirty, and **flush once** instead of per card.

```python
    def upsert(self, card: Card) -> Card:
        validate_card(card)                              # unchanged boundary (db.py:86)
        e = self._entry
        with e.lock:
            self._ensure_loaded()
            existing = e.by_id.get(card.id)
            if existing is not None:
                card = merge_cards(existing, card)       # unchanged (db.py:88-91)
            new_by_id = dict(e.by_id)
            new_by_id[card.id] = card
            e.by_id = new_by_id
            e.cards = tuple(sorted(new_by_id.values(), key=lambda c: c.id))  # keep id sort
            e.dirty = True
            if not self._in_batch:                       # default: flush every upsert
                self._flush_locked()
        return card

    def flush(self) -> None:
        e = self._entry
        with e.lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        e = self._entry
        if not e.dirty:
            return
        self._save(e.cards)            # existing _save (db.py:96-101) + fsync (below)
        st = self._stat_or_none()      # re-stat AFTER write so reload sees our own bytes
        if st is not None:
            e.mtime, e.size = st.st_mtime, st.st_size
        e.dirty = False
```

**Default behavior unchanged, opt-in batching.** With `_in_batch` defaulting False, every
`upsert` still writes to disk — byte-identical output, all `test_db.py`/`test_expand.py`/
`test_images.py` assertions that read the file mid-sequence keep passing. The speed win comes
from wrapping the ingest stages in a batch context so the ~2,400 upserts produce **one** write:

```python
    @contextlib.contextmanager
    def batch(self):
        self._in_batch = True
        try:
            yield self
            self.flush()
        finally:
            self._in_batch = False
            self.flush()    # flush even on exception so a partial scrape still persists
```

Apply at the call sites that loop upserts:
- `refresh_data` (`refresh.py:41`) — wrap the `expand_cards` + `enrich_cards` body in
  `with repo.batch():`. This is the O(n²) → O(n) win. The manifest loop's `find_by_id`
  (`refresh.py:75`) becomes O(1) automatically.
- `enrich_cards` (`enrich.py:57-103`) and `expand_cards` (`expand.py:60-71`) loops — either
  rely on the outer `refresh_data` batch, or wrap their own loops so `fc26 enrich`/`fc26 expand`
  CLI commands also batch.
- `images.upgrade` (`images.py:206-268`) — wrap the `_apply`→`upsert` writes (`images.py:215`).
  Note writes here are already serial (only the main thread calls `_apply` inside the
  `as_completed` loop at `images.py:253-257`), so a single repo + batch is correct.
- `cli.py:76-82` `seed` loop — wrap in `with repo.batch():`.

> Even **without** any batch context, the read cache alone already collapses each `upsert`'s
> `find_all()` re-parse to a no-op (served from RAM), so a large chunk of the O(n²) disappears
> on day one. Batching removes the remaining per-card *serialize+write*. Stage both.

### Atomic + durable write (`_atomic_write`, db.py:104-114)

The current `_atomic_write` already does temp-file → `os.replace` (atomic on POSIX + Windows
for 3.3+) — keep it. It is **missing durability**: no `fsync` on the temp file and no `fsync`
on the parent directory, so a crash/power-loss right after `os.replace` can leave a truncated
or zero-length file despite the rename being atomic. Add:

```python
def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())          # NEW: flush file contents to disk
        os.replace(tmp_name, path)
        dir_fd = os.open(path.parent, os.O_DIRECTORY)   # NEW: flush the rename itself
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
```

Guard `O_DIRECTORY`/dir-fsync for non-POSIX (it does not exist on Windows; wrap in a
`try/except (AttributeError, OSError)` or `if os.name == "posix"`). On macOS, plain `fsync`
does not fully flush to the platter (`F_FULLFSYNC` would), but `fsync` is the correct,
portable choice and is what `python-atomicwrites` and the established recipes use; do not
over-engineer. Batching makes fsync cost irrelevant — one fsync per refresh instead of 2,400.

---

## Invalidation & write strategy

Three actors touch the file; the strategy must keep all three correct.

| Actor | How it works today | Cache behavior needed |
|-------|-------------------|------------------------|
| **API reads** (`app.py` handlers) | `async def`, run **on the event loop** (serialized, single thread) — `asyncio.to_thread` is used only for the refresh loop (`app.py:89`). | Serve from cache. `_ensure_loaded` reloads if the file's mtime/size changed since last load — this is how the API picks up a refresh written by either the CLI or the in-process auto-refresh. |
| **Auto-refresh loop** (`app.py:75-101`) | Runs `refresh_data` in a worker thread via `asyncio.to_thread` (`app.py:89`), concurrent with `async def` read handlers. | This is the **one true concurrency point in serve.** Writes happen on the threadpool thread while reads happen on the event-loop thread. The per-entry `RLock` serializes write-vs-read. Because reads return an immutable snapshot tuple, a reader mid-iteration is never affected by a concurrent flush. |
| **CLI** (`cli.py`, fresh repo per process) | Each command constructs `CardRepository(db)`, does its work, process exits. | A fresh process = empty cache = one initial load = correct. No cross-process staleness because the process is short-lived. The CLI never needs to invalidate an API's cache (different process). |

**Cross-process correctness (CLI writes, running server reads):** if the user runs
`fc26 refresh` in one terminal while `fc26 serve` runs in another, the server's cache is
invalidated by the **mtime/size check** in `_ensure_loaded` — the next API read re-stats,
sees the changed file, and reloads. mtime+size together (not mtime alone) guards against the
same-second-write edge case where mtime resolution is coarse. This is the load-bearing reason
to track *both* `st_mtime` and `st_size`.

**Self-write must not trigger a redundant reload:** after `_flush_locked` writes, it re-stats
and stores the new mtime/size (shown above). Without this, the very next read would see "file
changed" (we changed it) and reload — re-parsing 4.4 MB we already hold. Re-stat-after-write
closes that loop.

**Dirty wins over disk:** while `e.dirty` is True (in-memory upserts not yet flushed), reads
must serve the in-memory snapshot, **not** reload from disk — otherwise a batched refresh would
read back stale pre-batch data mid-stream. The `if e.dirty: return` short-circuit in
`_ensure_loaded` enforces this. Since the default (non-batched) path flushes immediately,
`dirty` is only ever observed True inside a `batch()` context on the same thread holding the lock.

**Stale-cache-across-refresh pitfall (the headline risk):** the failure mode is "refresh wrote
new cards but the API keeps serving the old pool." Two defenses, both required: (1) re-stat on
every read so an external/CLI write is detected; (2) the in-process auto-refresh writes through
the **same** `_CacheEntry` (same path key), so its flush updates the shared cache directly —
the event-loop readers see new data on their next `_ensure_loaded` because the flush updated
`e.cards` in place and re-stamped mtime/size.

---

## Risks / pitfalls

### Critical

- **Per-request repo construction defeats a per-instance cache.** `app.py` builds
  `CardRepository(db_path)` in ~12 handlers. If the cache is an instance attribute it is
  rebuilt (and the file re-parsed) every request — zero benefit. **Mitigation:** process-global
  cache keyed by `path.resolve()`; the instance is a thin handle. This is non-negotiable for
  the API win.
- **Returning a mutable/live collection breaks iterate-while-upserting.** `enrich_cards`
  iterates `repo.find_all()` and upserts inside the loop (`enrich.py:57` + `:86`).
  **Mitigation:** `find_all` returns an immutable snapshot tuple (as today, `db.py:48`); upsert
  builds a *new* dict/tuple rather than mutating the one being iterated.
- **Stale cache across refresh** (detailed above). **Mitigation:** mtime+size re-stat on read,
  re-stat after self-write, dirty-wins-over-disk, shared entry for in-process refresh.
- **Write durability gap.** Current `_atomic_write` has no fsync (`db.py:104-114`); atomic
  rename without fsync can still lose/truncate data on power loss. **Mitigation:** fsync temp
  file + parent dir (guarded for non-POSIX). Cheap once writes are batched.

### Moderate

- **Thread-safety under the auto-refresh worker.** `refresh_data` runs on a threadpool thread
  (`app.py:89`) concurrently with event-loop reads. **Mitigation:** per-entry `RLock` around
  load/read/upsert/flush; reads hand back immutable snapshots so no reader holds a half-written
  structure. (Note: CPython's GIL makes dict get/set atomic, but the read-modify-write of
  upsert and the multi-field cache update are *not* atomic without the lock.)
- **Image-enrich concurrency assumption.** `test_images.py:181` explicitly documents "concurrent
  writers would clobber each other's upserts" and the design keeps `_apply` (the upsert) on the
  main thread only. **Mitigation:** keep that single-writer model; the lock is belt-and-braces.
  Do **not** push `repo.upsert` into the worker `_fetch` function.
- **`merge_cards` semantics must be preserved on cache hit.** Upsert merges when the id already
  exists (`db.py:88` → `merge.py:31`), and `_resolve` in expand suffixes ids on ovr collision
  (`expand.py:84-97`). The cached upsert must call `merge_cards` identically and keep the
  by-id index consistent with the suffixed id. **Mitigation:** mirror `db.py:87-93` exactly,
  only swapping the data source from `find_all()` to the cached `by_id`.
- **Sort-by-id on save must stay.** `_save` sorts cards by `c.id` (`db.py:99`); the on-disk
  byte order depends on it. **Mitigation:** keep `tuple(sorted(..., key=lambda c: c.id))` when
  building the snapshot for flush so output stays byte-identical.

### Minor

- **Test isolation across tmp_path repos.** Tests construct many repos on distinct `tmp_path`
  files; a process-global cache keyed by resolved path keeps them isolated automatically. But
  if any test reuses a path or mutates a file out-of-band, add a `CardRepository._reset_cache()`
  test hook (or clear `_CACHES` in a fixture) to avoid cross-test bleed. **Mitigation:** expose
  a private reset and call it in a pytest autouse fixture if any flakiness appears.
- **macOS `fsync` is not `F_FULLFSYNC`.** Acceptable; portable fsync is the documented norm.
- **mtime resolution on some filesystems is coarse (1s).** Size check covers same-second,
  same-mtime, different-content writes. Keep both.

---

## Verification approach (prove behavior is unchanged)

**Existing safety net for `db.py` (must stay green, unchanged):**
- `tests/test_db.py` — roundtrip, missing-file→`()`, upsert/find_by_id, no-duplicate upsert,
  boundary validation, search case-insensitivity, corrupt JSON → `DatabaseError`,
  schema_version presence/mismatch. This is the core contract; do not edit these to make a
  cache pass — if they fail, the cache changed behavior.
- `tests/test_expand.py` — exact `new`/`merged` counts (`:36-37,50-51,62`), id-suffix on ovr
  collision (`:60-73`). Guards that batched upsert keeps the new-vs-merged signal and `_resolve`.
- `tests/test_enrich.py` — iterate-while-upsert (`:57`+`:86` exercised), id-change-on-rename
  (`:119,156-167`), counts. Guards the snapshot-read invariant.
- `tests/test_images.py` — single-writer-under-workers invariant explicitly asserted
  (`:181,193`), "every card lands". Guards thread-safety + batch-flush completeness.
- `tests/test_search.py`, `tests/test_cli.py` — read-path and CLI-construction coverage.

**Add (new tests for the cache itself):**
1. **mtime/size invalidation:** load via repo A, externally rewrite the file (simulating a CLI
   write), assert repo B (or a re-read) returns the new content. Then write with identical
   size+mtime but different bytes (force-set mtime) and assert size-or-content still reloads.
2. **Self-write no-redundant-reload:** spy/count `json.loads` (or wrap `_parse_file`); assert N
   upserts in a `batch()` cause exactly **one** parse and **one** `_atomic_write`.
3. **Snapshot stability:** hold `t = repo.find_all()`, upsert a new card, assert `t` is
   unchanged (still the old tuple) and a fresh `find_all()` reflects the change.
4. **Concurrency smoke:** spawn a thread doing upserts while the main thread does `find_all`
   in a loop; assert no exception and final state is consistent (mirrors the
   serve worker-vs-event-loop split).
5. **fsync called:** monkeypatch `os.fsync` to count calls; assert it fires on flush.
6. **Byte-identical output:** capture `data/players.json` bytes before/after a no-op
   refresh-style sequence through the cached path vs. the old direct path; assert equal
   (this is the milestone's "zero behavior change" gate).

**Benchmark harness (none exists today — PROJECT.md flags this):**
- **Refresh write cost:** time `refresh_data` against a fixture pool of ~2,400 cards with a
  stubbed `fetch_html`. Metric: total `upsert` wall time and count of `_atomic_write` calls
  (expect drop from ~2,400 to 1) and `json.dumps`/`json.loads` calls (expect O(n²)→O(n)).
- **API read cost:** time repeated `GET /api/cards` / `/api/meta` (`app.py:157,327`); metric is
  per-request latency with cold vs warm cache — expect the second+ request to do **zero**
  `json.loads`. Also `find_by_id` micro-bench: O(n) scan (`db.py:62-66`) vs O(1) index, and
  `_squad_positions`' up-to-11 `find_by_id` calls (`app.py:408`).
- Establish baselines on `ro` HEAD first (capture numbers), then re-run after the cache to
  prove the speedup and guard against regression in CI.

---

## Confidence levels

| Claim | Confidence | Basis |
|-------|-----------|-------|
| Per-request `CardRepository(db_path)` + full parse is the API read cost | HIGH | Read `app.py` directly (~12 construction sites); matches CONCERNS 3.1 |
| `upsert` is per-card full parse+serialize → O(n²) refresh | HIGH | Read `db.py:85-101`; self-flagged `db.py:83-84`; CONCERNS 1.1 |
| Process-global, path-keyed cache is required (instance cache fails) | HIGH | Direct consequence of per-request construction in `app.py` |
| `find_all` must return immutable snapshot (iterate-while-upsert) | HIGH | Read `enrich.py:57`+`:86`; `card_from_dict` yields frozen dataclasses |
| Serve is single-process; only refresh worker + image pool are concurrent | HIGH | `uvicorn.run(api,...)` no `workers=` (`cli.py:730`); `asyncio.to_thread` only at `app.py:89`; ThreadPool writes serial at `images.py:253-257` |
| API handlers are `async def` → run on event loop, not threadpool | HIGH | Read all handler signatures in `app.py` |
| `os.replace` is atomic; fsync (file+dir) needed for durability | HIGH | Python docs + python-atomicwrites + established recipes (sources below) |
| Sync-`def` FastAPI endpoints run in a threadpool (general) | HIGH | FastAPI docs (sources below) — informs why footie's all-async handlers serialize on the loop |
| mtime+size invalidation is sufficient for CLI-write/server-read | MEDIUM | Standard pattern; coarse-mtime edge case mitigated by size; verified by reasoning, not a footie-specific test yet |
| macOS plain `fsync` ≠ full platter flush (`F_FULLFSYNC`) | MEDIUM | Search consensus; acceptable for this use case |

---

## Sources

- [python-atomicwrites (untitaker)](https://github.com/untitaker/python-atomicwrites) — temp+rename+fsync(file)+fsync(dir) reference implementation
- [python-atomicwrites docs](https://python-atomicwrites.readthedocs.io/)
- [Python os.replace — guide](https://zetcode.com/python/os-replace/) — atomic replace, cross-platform
- [Python os.fsync — guide](https://zetcode.com/python/os-fsync/) — flush-to-disk semantics, F_FULLFSYNC on macOS
- [PSA: Avoid Data Corruption by Syncing to Disk](https://blog.elijahlopez.ca/posts/data-corruption-atomic-writing/) — why rename-without-fsync still loses data
- [Adding atomicwrite in stdlib — Python.org discussion](https://discuss.python.org/t/adding-atomicwrite-in-stdlib/11899)
- [FastAPI — Concurrency and async/await](https://fastapi.tiangolo.com/async/) — sync `def` → threadpool; `async def` → event loop
- [The Concurrency Trap in FastAPI (global state race conditions)](https://datasciocean.com/en/other/fastapi-race-condition/) — shared state needs locks; thread-local stack frames are isolated
