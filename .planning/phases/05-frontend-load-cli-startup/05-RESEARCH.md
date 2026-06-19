# Phase 5 Research — Frontend Load & CLI Startup

**Phase:** 5 (final) · **Requirements:** WEB-01, WEB-02, WEB-03, CLI-01
**Date:** 2026-06-19 · **Confidence:** HIGH (Vite 6/Rollup, React 19 lazy, TanStack Query v5, deferred-import idiom all verified at file:line)
**Primary source:** `.planning/research/FRONTEND-TOOLING.md` §A (frontend) + §B4 (CLI). §B1–B3 (benchmark harness) already shipped in Phase 1 — not in scope here.

## Two independent workstreams (parallel, different files)
- **Frontend** (`web/`): WEB-01/02/03 — route code-splitting, dead-dep removal, React Query tuning. Plan 05-01.
- **CLI** (`fc26/cli.py`): CLI-01 — deferred heavy imports. Plan 05-02.
They share no files → both Wave 1, fully parallel.

## Constraint (milestone-wide)
ZERO observable behavior change: rendered pages identical (vitest + e2e), API responses identical, **CLI text byte-identical** (golden cli_list/cli_show + test_cli). The bundle *bytes* change **by design** (that is the WEB deliverable) — measured via before/after `vite build`, not goldened. All existing tests green.

## Frontend (verified at file:line)

### WEB-01 — route code-splitting (`web/src/App.tsx`)
`App.tsx:3-13` eagerly imports all 11 pages → one entry chunk holds every page incl. `GeneratorPage` (which pulls the `@imgly` WASM/ML graph). Fix: convert each static page import to `React.lazy(() => import('./pages/X'))` at **module top level** (never inside the component — react.dev) and wrap `<Routes>` in one `<Suspense fallback={<SkeletonGrid />}>`. Verified: all 11 `pages/*.tsx` are default exports (`grep export default` → 11/11); `SkeletonGrid` is a default export (`components/SkeletonGrid.tsx:1`), reusable as the fallback (matches existing UX). App uses the declarative `<BrowserRouter>`+`<Routes>` API (`main.tsx:13`), so `React.lazy` is the right tool (NOT react-router's data-router `lazy` route prop).

### WEB-02 — heavy/WASM dep + dead dep
- `@imgly/background-removal` is **already** dynamically imported (`GeneratorPage.tsx:272` `await import('@imgly/background-removal')`). Once WEB-01 makes GeneratorPage lazy, the `@imgly` chunk only loads on `/create` + photo upload. No GeneratorPage change needed. Do NOT add it to optimizeDeps/manualChunks.
- `html-to-image@^1.11.13` (`package.json` deps) is **unused** — `grep -rn html-to-image src/` → 0 matches; PNG export uses native `canvas.toDataURL` (`GeneratorPage.tsx:46,107,402`). Remove from `package.json` deps (behavior-preserving).
- (Optional, low-risk) `vite.config.ts` `build.rollupOptions.output.manualChunks` object-form vendor split: `react-vendor: [react, react-dom, react-router-dom]`, `query-vendor: [@tanstack/react-query]`. Vite 6 = Rollup (`rollupOptions`, NOT rolldownOptions). Object form only; do NOT function-form route-split (React.lazy owns page chunks) and do NOT put `@imgly` in a group.

### WEB-03 — React Query tuning (`web/src/main.tsx:8`)
Bare `new QueryClient()` → TanStack v5 defaults (`staleTime:0`, refetch-on-mount/focus) refetch `/api/meta` + `/api/cards` on every nav/focus. Fix: `defaultOptions.queries = { staleTime: 5*60_000, gcTime: 30*60_000, refetchOnWindowFocus: false, retry: 1 }`. Then the now-redundant per-query `staleTime` in `cards.ts:53` (`useAllCards`) can be dropped (or left). Changes *when* it refetches, not *what* the API returns — the intended kind of perf change. `App.test.tsx` builds its own QueryClient (retry:false) so the global default doesn't affect tests.

### Test impact (verified — no rewrites needed)
- `App.test.tsx` uses `findByText`/`findByRole` (async) → waits through the Suspense fallback → stays green with lazy pages. It wraps App in its own QueryClient+MemoryRouter (Suspense lives inside App).
- `e2e/app.spec.ts` waits on page **content** with timeouts (`getByText(/\d+ cards/)`, 15–30s) → resilient to the brief Suspense fallback. No spinner-absence assertions.
- Per-page vitest tests render pages directly → unaffected by App-level lazy.

## CLI (verified at file:line)

### CLI-01 — deferred imports (`fc26/cli.py`)
`cli.py:12-44` imports at module load: `httpx`, `rich`, and the **whole** builder/chem/ingest/db/models graph — `.ingest.*` parsers pull **selectolax**, `.ingest.web`/`web_async` + line 12 pull **httpx**. So `fc26 --help` / `fc26 search` pay the full scrape+builder import cost they never use. Fix: move the heavy imports into the command bodies that use them (the idiom `serve` already uses — uvicorn/create_app deferred at `cli.py:715-716`).
- **Keep at top** (light + needed broadly incl. fast `search`/`list`/`show`): `typer`, `Path`, `json as json_lib`, `time`, `asdict`, `NoReturn`, `asyncio`, `rich` (console/table), `.db` (CardRepository — light, no selectolax/httpx), `.errors`, `.models`, and the option constants (`DB_OPTION`/`JSON_FLAG` need values at decoration time).
- **Defer into command bodies**: every `from .builder.*`, `from .chem.*`, `from .ingest.*` (incl. `web`/`web_async`/`AsyncFetcher`/the `_async` fns), and top-level `import httpx`. Mapping (FRONTEND-TOOLING §B4): ingest→`add/sync/enrich/expand/images/refresh/refresh-objectives/refresh-sbcs`; builder/chem→`build/upgrade/plan/chem/advise/boost`; httpx→the scraper commands that catch `httpx.HTTPError`.
- PEP 810 lazy imports N/A on Python 3.12/3.14 — manual deferral only.
- Behavior-equivalence: deferral changes *when* a module loads, not *what* a command does — identical output + identical `FC26Error` handling. Verified idiom; 50–80% startup cuts reported.

## Validation Architecture

> nyquist_validation `true`

### Frameworks
| Surface | Tooling |
|---------|---------|
| Web unit | vitest (`web/ && npm run test`), jsdom + MSW; coverage thresholds 80% (`vite.config.ts`) |
| Web build | `npm run build` (tsc -b + vite build) — must succeed; inspect chunk list |
| Web e2e | Playwright (`npm run e2e`) — content-waited, resilient (run if a serve env is available; otherwise rely on vitest + manual) |
| CLI text | pytest golden (`FORCE_COLOR= NO_COLOR=1 pytest -m golden --run-bench`) + `tests/test_cli.py` (62 tests) |
| CLI startup | subprocess import check (deterministic) + `python -X importtime -m fc26 --help` (before/after number) |

### Requirements → test map
| Req | Behavior | Test | Exists? |
|-----|----------|------|---------|
| WEB-01 | pages are separate lazy chunks; app still renders/routes | `npm run test` (App.test routes) + `npm run build` chunk list (one chunk/page, smaller entry) | ✅ App.test + ❌ build-size check (manual/scripted) |
| WEB-02 | `@imgly` only in its own chunk (not entry); `html-to-image` removed | `npm run build` chunk list (separate @imgly chunk) + `grep html-to-image` gone + deps install clean | ✅ grep + ❌ build inspect |
| WEB-03 | QueryClient defaultOptions set; no refetch-on-focus; data identical | `npm run test` green (App.test + page tests) | ✅ vitest |
| CLI-01 | heavy deps not imported at CLI load; `--help`/commands faster; output identical | subprocess: `selectolax`/`httpx` absent from `sys.modules` after `import fc26.cli`; `test_cli.py` 62 green; golden cli unchanged | ✅ test_cli + golden + ❌ W0 import-cost test |
| (all) | existing tests green; CLI golden byte-identical | `pytest -q`, `npm run test`, golden | ✅ |

### Wave 0
- `tests/test_cli_startup.py` — subprocess `python -c "import sys, fc26.cli; assert not ({'selectolax','httpx'} & sys.modules.keys())"` exits 0 (proves deferral). Default-suite test (no marker), fast.
- Web: no new unit test file needed (App.test + page tests already cover render/route). The build-size before/after is captured in the summary (run `npm run build` pre/post, record entry + chunk sizes). No golden for bundle bytes (they change by design).

## Security domain
No new runtime surface. Frontend: removing an unused dep shrinks supply-chain surface (net positive); React Query tuning + code-split don't change auth/data. CLI: deferred imports don't change what runs. `@imgly` stays behind the existing dynamic import (no eager WASM). ASVS: none directly applicable.

## Sources
- `.planning/research/FRONTEND-TOOLING.md` §A1–A6, §B4 (verified Vite 6/Rollup manualChunks, React 19 lazy, TanStack v5 defaults, deferred-import idiom).
- Code (read directly): `web/src/{App,main}.tsx`, `web/vite.config.ts`, `web/src/api/cards.ts`, `web/src/App.test.tsx`, `web/e2e/app.spec.ts`, `web/package.json`, `web/src/components/SkeletonGrid.tsx`, `web/src/pages/GeneratorPage.tsx` (lines 46/107/272/402), `fc26/cli.py:1-55`.
- Phase 1 golden (cli_list/cli_show) + benchmark harness (no new harness needed).
