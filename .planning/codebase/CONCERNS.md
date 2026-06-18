# Performance Bottleneck Inventory

**Analysis Date:** 2026-06-17
**Purpose:** Raw material for the "performance/speed improvements" milestone. Evidence-based; grouped by the 4 target areas. No fixes prescribed here.

**Root cause spanning areas 1 & 3:** the "DB" is a single ~4.4 MB JSON file (`data/players.json`, ~2,434 cards). `fc26/db.py` re-reads/re-parses (and on write re-serializes) the entire file on essentially every operation.

## Area 1 — Scrapers / Ingest
- **1.1 O(n²) full-file rewrite per `upsert` — HIGH.** `db.py:85` → `find_all` (parse all cards) + `_save` (re-serialize+write whole 4.4 MB) per card. A refresh upserts ~2,400 cards → millions of (de)serializations. Self-flagged `db.py:83-84`.
- **1.2 Strictly sequential HTTP with 1–2s sleeps — HIGH.** `expand.py:46-75`, `enrich.py:57-103`, `refresh.py:51-68`; jitter `refresh.py:29-32`. Only `images.py` is concurrent.
- **1.3 No HTTP connection reuse — MED.** Module-level `httpx.get` everywhere (`web.py:18`, `futgg.py`, `fcratings.py`, `sbc.py`, `objectives.py`) → fresh TCP+TLS per request; no shared `httpx.Client`.
- **1.4 Repeated regex/DOM passes over large HTML per card — MED.** `futgg.py:219-388` (~20+ regex scans + parser tree builds); `_extract_playstyles` compiles regex inline per call.
- **1.5 `find_by_id` O(n) full scan inside ingest loops — MED/HIGH.** `db.py:62-66`; `_resolve` calls it up to twice/card (`expand.py:91/94`); manifest builds ≤200 more scans (`refresh.py:72-76`).

## Area 2 — Web App Load
- **2.1 No route code-splitting; single ~298 KB JS bundle — HIGH.** `App.tsx` eagerly imports all ~12 pages. Only one `import()` exists (`GeneratorPage.tsx:272`). No `React.lazy`/`Suspense`.
- **2.2 Heavy client deps in graph — MED.** `@imgly/background-removal` (WASM+model), `html-to-image`; GeneratorPage in main bundle.
- **2.3 Bare `new QueryClient()` (staleTime 0) — MED.** `main.tsx:8`; refetch-on-mount/focus re-triggers `/api/meta` + `/api/cards` on every navigation though meta is static between refreshes. (Note: `useAllCards` overrides staleTime 5min — inconsistent caching.)

## Area 3 — API / Backend + DB
- **3.1 New repo + full 4.4 MB read per request — HIGH.** `CardRepository(db_path)` + `find_all()` per handler (`app.py:186,220,259,269,285,300,329,355,432,408`). No in-memory cache.
- **3.2 Blocking I/O + CPU inside `async def` handlers — HIGH.** Handlers (`app.py:157-459`) call blocking `find_all`/builders on the event loop; `asyncio.to_thread` used only for refresh loop → requests serialize.
- **3.3 `/api/meta` full-pool scan per call — MED.** `app.py:327-342` recomputes leagues/nations/clubs/versions sets from all cards though they change only on refresh.
- **3.4 N+1 full-file scans in `_squad_positions` — MED.** `app.py:395-412`; `find_by_id` per XI card → up to 11 full-file parses per `/api/value?squad=`.
- **3.5 Build/upgrade do tens–hundreds of thousands of chem recomputes per request — HIGH.** `upgrade.py:87-169` = rounds×11×~2,400 candidates × `compute_chemistry`; `/api/build` (`BUILD_MAX_SWAPS=11`) ≈ hundreds of thousands; `compute_chemistry` rebuilds Counters + re-canonicalizes per call (`engine.py:87-160`); all on the event loop.
- **3.6 `slugify`/`canonical_*` not memoized — MED.** `aliases.py:59-76` + `models.py:98-100` (unicode normalize + regex) called inside the large loops.
- **3.7 SPA fallback `.resolve()` per request — LOW.** `app.py:464-475`.

## Area 4 — CLI Startup + Test Suite
- **4.1 CLI eagerly imports entire app graph — MED.** `cli.py:11-36` imports httpx, typer, rich, selectolax + all builder/chem/ingest modules; even `--help` pays full cost.
- **4.2 `Console(width=200)` + rich at import — LOW.** `cli.py:39`.
- **4.3 Test suite already offline-safe — LOW.** Live tests gated; parser tests use fixtures. Large suite inherits per-`upsert` full-rewrite cost on temp fixtures but stays offline/deterministic.

## Prioritized Top Bottlenecks
1. JSON "DB" re-read/rewritten in full per op (`db.py:48/85/96`) — root cause; refresh O(n²), every API call re-parses whole file. **HIGH**
2. Every API handler re-reads the full file inside blocking `async def` (`app.py`) — no cache, serializes event loop. **HIGH**
3. `/api/build` & `/api/upgrade` do tens–hundreds of thousands of chemistry recomputes per request (`builder/`). **HIGH**
4. Ingest strictly sequential with 1–2s sleeps and no connection reuse. **HIGH**
5. Web app ships one un-split ~298 KB JS bundle (all pages eager). **HIGH**
6. N+1 / O(n) `find_by_id` scans + un-memoized `slugify`/`canonical_*` compound the above. **MED**
7. `/api/meta` recomputes static dropdowns every call; React Query refetch-on-nav. **MED**
8. CLI eagerly imports whole package, inflating startup. **MED**
