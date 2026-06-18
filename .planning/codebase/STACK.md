# Technology Stack

**Analysis Date:** 2026-06-17

## Languages
- **Python `>=3.12`** (`pyproject.toml:5`) — all backend code under `fc26/`.
- **TypeScript `^5`** (`web/package.json`) — SPA under `web/src/`, strict bundler-mode (`web/tsconfig.json`).
- HTML/CSS via Tailwind v4 (`web/src/index.css`, plugin `web/vite.config.ts`).

## Runtime
- **Backend:** CPython 3.12+; setuptools package `fc26` (`pyproject.toml:21-26`). ASGI via `uvicorn>=0.30` running `create_app` (`fc26/api/app.py:104`); single event loop, blocking work occasionally offloaded with `asyncio.to_thread`.
- **Frontend:** Node ESM project; React 19 SPA served by Vite dev (5173) or static from `web/dist` by FastAPI (`fc26/api/app.py:464-475`).
- **Package managers:** pip+setuptools (**no Python lockfile** — deps pinned only with `>=`); npm with committed `web/package-lock.json`.

## Frameworks / Libraries
- **CLI:** `typer>=0.12` (`fc26/cli.py:38`, console script `fc26=fc26.cli:app`, `pyproject.toml:18-19`); `rich>=13` output.
- **API:** `fastapi>=0.111` (`fc26/api/app.py:157-475`, CORS locked to `:5173`).
- **Scraping:** `httpx>=0.27` (`fc26/ingest/web.py:5`) + `selectolax>=0.3` (HTML parsing).
- **Frontend:** React `^19`, `react-router-dom ^7`, `@tanstack/react-query ^5`, build via `vite ^6` + `@vitejs/plugin-react` + `@tailwindcss/vite`; build runs `tsc -b && vite build` → `web/dist`.
- **Heavy client deps:** `@imgly/background-removal ^1.7` (WASM/ML model, large), `html-to-image ^1.11`.

## Data Storage
- **No SQL database.** `fc26/db.py` is a **JSON-file repository** (`CardRepository`); the only store is `data/players.json` (~4.4 MB, ~2,434 cards as of 2026-06-17). Default path `data/players.json` (`fc26/cli.py:41`, `--db` override).

## Test Tooling
- **Backend:** `pytest>=8` + `pytest-cov>=5` (`pyproject.toml:16`); `live` marker opt-in via `--run-live` (`pyproject.toml:29`, `tests/conftest.py`) — default run is offline.
- **Frontend:** `vitest ^2` + jsdom + `@testing-library/react` + `msw ^2`; v8 coverage with 80% thresholds (`web/vite.config.ts`).
- **E2E:** `@playwright/test ^1.48` (`web/playwright.config.ts`): `workers:1`, `fullyParallel:false`, boots real `fc26 serve` on 8026.

## Entry Points
- CLI `fc26 <command>` (`fc26/cli.py`).
- API `fc26 serve` → `create_app` under uvicorn; optional auto-refresh loop in lifespan (`fc26/api/app.py:75-126`).
- Refresh pipeline `refresh_data` (`fc26/ingest/refresh.py:41`) → `expand_cards` → `enrich_cards`, shared by CLI and auto-refresh.
- Web: `npm run dev` (5173) / `npm run build` (served by FastAPI) / `npm run e2e`.

## Performance-Relevant Characteristics
- **JSON store re-read/rewritten in full per op:** `find_all()` parses entire file + rebuilds dataclasses each call (`fc26/db.py:48-60`); no in-memory cache; fresh `CardRepository` per request (`app.py:186,220,259,...`). `upsert` re-reads + rewrites whole file (`db.py:85-101`; code comment assumes "n~150", now 2,434).
- **HTTP sync, no pooling:** module-level `httpx.get` (`fc26/ingest/web.py:18`) — new connection per request, no shared `Client`/`AsyncClient`, no keep-alive; 15s timeout, 1 retry.
- **Scraping sequential + throttled:** deliberate `REQUEST_DELAY_SECONDS=1.0` (`enrich.py`) + 0–100% jitter (`refresh.py:29-32`). Only image enrichment is threaded (`images.py` ThreadPoolExecutor), but each worker `upsert`s the full file.
- **Web bundle:** Vite 6 with default chunking — no `manualChunks`/`rollupOptions` in `web/vite.config.ts`; heavy deps not explicitly code-split; SPA served via per-request `FileResponse` with no cache headers.
- **Tests:** default pytest fast/offline; slow tier is opt-in live tests + serial Playwright e2e booting the real stack. **No benchmark/profiling harness exists.**
