# Phase 5 Verification — Frontend Load & CLI Startup

**Date:** 2026-06-19 · **Verdict:** ✅ PASSED (final phase — milestone complete)
**Goal:** The web app's initial download shrinks and navigation stops refetching static data, and the CLI starts fast for `--help`/simple commands.

## Requirement-by-requirement (goal-backward)

| Req | Verdict | Evidence |
|-----|---------|----------|
| **WEB-01** routes code-split, smaller initial bundle | ✅ | `App.tsx` all 11 pages `React.lazy` + one `Suspense`. Build: each page its own chunk; entry `index` 336→189 kB; pages no longer in initial download. vitest 72 passed (render/route unchanged). |
| **WEB-02** heavy/WASM dep lazy + dead dep removed | ✅ | `@imgly`/onnxruntime (`ort.*` ~399 kB ×2) are separate chunks NOT in `index.html` (only fetched on `/create`+upload); `html-to-image` removed from `package.json` (`grep -rn html-to-image web/src` empty); vendor `manualChunks` (react-vendor/query-vendor). |
| **WEB-03** React Query tuned, no refetch of static data | ✅ | `main.tsx` `QueryClient` `defaultOptions.queries` = staleTime 5m / gcTime 30m / refetchOnWindowFocus false / retry 1; redundant per-query staleTime dropped from `useAllCards`. Data returned unchanged (vitest green). |
| **CLI-01** defer heavy imports, fast startup | ✅ | `import fc26.cli` no longer pulls selectolax/httpx; `sys.modules` 416→273 (−34%). Heavy graph deferred into command bodies; `DEFAULT_*` moved to light `fc26/ingest/constants.py`. `tests/test_cli_startup.py` subprocess gate green. |
| (all) | ✅ | existing tests green; CLI text byte-identical |

## Behavior-equivalence (the hard constraint)
- **CLI text byte-identical:** golden `cli_list`/`cli_show` 10 passed; `tests/test_cli.py` 62 green (output/exit codes unchanged; only monkeypatch targets retargeted to source modules).
- **Web behavior:** vitest 72 passed under lazy/Suspense (App.test async `findBy*` survives the fallback); `npm run build` succeeds. Bundle *bytes* change by design (the WEB deliverable); rendered output + API data unchanged.
- e2e (Playwright) not run here (needs a live `fc26 serve`); specs are content-waited + resilient — manual/optional.

## Gates
- Python full suite: **365 passed, 29 skipped** (was 364 + 1 new startup test).
- Golden byte-identical: **10 passed**.
- Web vitest: **72 passed (20 files)**; `npm run build` green.
- `from fc26.api.app import create_app` clean (DEFAULT_* re-export intact).

## Files changed
Frontend: `web/src/App.tsx`, `web/src/main.tsx`, `web/src/api/cards.ts`, `web/package.json`(+lock), `web/vite.config.ts`. CLI: `fc26/ingest/constants.py` (new), `fc26/ingest/refresh.py`, `fc26/cli.py`, `tests/test_cli.py`, `tests/test_cli_startup.py` (new).

## Notes carried forward
- `console = Console(width=200)` left at module top (research flagged lazifying it as a lower-priority follow-on — out of scope).
- `useAllCards` payload trimming (`?limit=5000`) intentionally NOT done (would change client data; research marked it stretch/optional, backend cache is the bigger lever — already shipped in Phase 2).
- e2e + real-browser network verification left as a manual check (needs serve env).
