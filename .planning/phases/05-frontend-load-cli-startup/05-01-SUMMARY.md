# 05-01 SUMMARY — Frontend load

**Status:** ✅ complete · **Wave:** 1 · **Requirements:** WEB-01, WEB-02, WEB-03

## What was built
- **WEB-01** `App.tsx`: all 11 pages converted to `React.lazy(() => import(...))` at module top level, `<Routes>` wrapped in one `<Suspense fallback={<SkeletonGrid />}>`. Each page is now its own chunk.
- **WEB-02**: removed the unused `html-to-image` dep from `package.json` (PNG export uses `canvas.toDataURL`); `@imgly/background-removal` stays behind its existing dynamic import (`GeneratorPage.tsx:272`) → its onnxruntime graph leaves the initial download. Added object-form `manualChunks` vendor split (`react-vendor`, `query-vendor`) to `vite.config.ts` (Vite 6 = Rollup `rollupOptions`).
- **WEB-03** `main.tsx`: `QueryClient` now has `defaultOptions.queries` = `{ staleTime: 5m, gcTime: 30m, refetchOnWindowFocus: false, retry: 1 }`. Dropped the now-redundant per-query `staleTime` on `useAllCards` (`cards.ts`).

## Before / after (production build)
| | Before | After |
|---|--------|-------|
| Initial JS (index.html: entry + preloaded vendors) | one entry `index` **336.47 kB** (gzip 103.03) | entry `index` **188.62 kB** (gzip 59.81) + `react-vendor` 40.87 + `query-vendor` 49.98 = **~279 kB** (gzip ~90) |
| Pages in initial bundle | all 11 (eager) | **0** — each is a lazy chunk (CardsPage 5.4 kB … GeneratorPage 13.8 kB) |
| `@imgly`/onnxruntime (`ort.*` ~399 kB ×2) | reachable from eager GeneratorPage | separate chunks, NOT in `index.html` — only fetched on `/create` + photo upload |
| `html-to-image` | declared dep | removed |

Per-user-route the win is larger: landing on `/cards` now pulls entry+vendors+CardsPage (~5 kB) instead of a bundle containing every page.

## Verification
- `cd web && npm run test` → **72 passed (20 files)** — render + routing under lazy/Suspense unchanged (App.test uses async findBy*, survives the fallback).
- `cd web && npm run build` → succeeds; per-page chunks + separate `@imgly`/`ort` chunks + `react-vendor`/`query-vendor`; entry 336→189 kB.
- `grep -rn html-to-image web/src` → none.
- e2e (Playwright) not run here (needs a live `fc26 serve` env); specs are content-waited and resilient to the Suspense fallback (verified in research) — left as a manual check.

## Decisions
- Kept the optional vendor `manualChunks` (clean split, no warnings). `@imgly` intentionally NOT grouped (stays behind dynamic import).
- No behavior change: rendered output + API data identical; only load timing + bundle shape changed.
