# Architecture

**Analysis Date:** 2026-06-17

## Shape
A layered data pipeline with two entry points over a single JSON store:

```
scrape (fc26/ingest) → parse → merge (fc26/merge.py) → JSON store (fc26/db.py, data/players.json)
                                                              │
                          pure compute (fc26/chem, fc26/builder)
                                                              │
                          ┌───────────────┴───────────────┐
                     CLI (fc26/cli.py)            API (fc26/api/app.py)
                                                              │
                                                 React/Vite SPA (web/src) via /api/*
```

## Module Map (`fc26/`)
- **`errors.py`** — typed hierarchy `FC26Error` → `DatabaseError`, `FetchError`, `ParseError`.
- **`models.py`** — immutable frozen dataclasses (domain model); `canonical_*` normalization helpers (`models.py:98-100`).
- **`db.py`** — `CardRepository` over `data/players.json`: `find_all`, `find_by_id`, `search`, `upsert`.
- **`ingest/`** — scrapers: `web.py` (fetch), `futgg.py`, `fcratings.py`, `futbin.py`, `sbc.py`, `objectives.py`, `images.py`; orchestration `expand.py`, `enrich.py`, `refresh.py`.
- **`merge.py`** — reconcile/dedupe scraped records.
- **`chem/`** — chemistry engine (`engine.py compute_chemistry`), rules, styles, lineup.
- **`builder/`** — squad build (`build.py`) + upgrade search (`upgrade.py`).
- **`api/app.py`** — FastAPI app; `{ok,data,error}` response envelope; also static-serves `web/dist`.
- **`cli.py`** — typer commands (build, serve, refresh, search, ...).

## Data Flow
1. **Refresh:** `refresh_data` → `expand_cards` (discover card ids) → `enrich_cards` (per-card detail fetch) → `upsert` into JSON. Default interval 72h; full non-incremental re-scrape.
2. **Read (API/CLI):** construct `CardRepository`, `find_all`, filter/sort/compute in Python, return.
3. **Web:** SPA fetches `/api/*` (envelope) via TanStack Query; `useAllCards()` pulls `?limit=5000` (whole pool) with 5-min `staleTime`.

## Key Boundaries
- Compute layers (`chem`, `builder`) are **pure** with dependency injection (`fetch_html`, `sleep`, `on_progress`) → CLI and API share identical logic; API is stateless (no cache).
- Build/dependency order: `errors → models → merge → db → {ingest, chem → builder} → cli/api`. SPA builds independently and is mounted same-origin by `fc26 serve`.

## Performance-Relevant Flow Notes
- **`upsert` rewrites the whole ~4.4 MB file per card** (`db.py:85-101`) → refresh is effectively O(n²) in serialization.
- **`refresh_data` is a full re-scrape every 72h** — no incremental/delta.
- **Every read endpoint re-reads + re-filters/recomputes the full pool** with no cache (`app.py:186,220,259,329,355`).
- **`_squad_positions` does up to 11 `find_by_id` full-file scans** per `/api/value?squad=` (`app.py:408-409`).
- **Build/upgrade recompute chemistry in O(slots×pool) loops** — tens to hundreds of thousands of `compute_chemistry` calls per request (`builder/upgrade.py:87-169`, `build.py`).
- **SPA pulls the entire pool** via `useAllCards` `?limit=5000` (`web/src/api/cards.ts`).
