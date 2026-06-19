---
phase: 5
slug: frontend-load-cli-startup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-19
---

# Phase 5 — Validation Strategy

> Phase 5 is two independent pure-speedup workstreams: (1) frontend — route code-splitting (`App.tsx`), dead-dep removal + optional vendor chunk split (`package.json`/`vite.config.ts`), React Query tuning (`main.tsx`/`cards.ts`); (2) CLI — deferred heavy imports (`cli.py`). The bundle *bytes* change by design (the WEB win); all observable behavior stays identical — rendered pages (vitest + e2e), API responses, and **CLI text byte-identical** (golden + test_cli). All existing tests green.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Web unit** | vitest — `cd web && npm run test` (jsdom + MSW; coverage 80% thresholds in `vite.config.ts`) |
| **Web build** | `cd web && npm run build` (`tsc -b && vite build`) — must succeed; inspect emitted chunk list |
| **Web e2e** | Playwright — `cd web && npm run e2e` (content-waited specs; run if a serve env is available) |
| **Python** | pytest >=8 — `FORCE_COLOR= NO_COLOR=1 pytest -q` |
| **CLI text gate** | `FORCE_COLOR= NO_COLOR=1 pytest -m golden --run-bench` (cli_list/cli_show byte-identical) + `tests/test_cli.py` |
| **CLI startup gate** | subprocess import check (deterministic) + `python -X importtime -m fc26 --help` (before/after number) |
| **Env note** | `FORCE_COLOR=3` set → ALWAYS prefix `FORCE_COLOR= NO_COLOR=1` or 5 CLI tests show spurious ANSI failures |
| **Setup note** | exec worktree needs `cd web && npm install` (frontend) and a `.venv` with `pip install -e ".[dev]"` (Python) |

---

## Sampling Rate

- **Per task commit:** the touched surface's quick gate — `npm run test` (frontend tasks) or `FORCE_COLOR= NO_COLOR=1 pytest tests/test_cli.py tests/test_cli_startup.py -q` (CLI task).
- **Per wave:** `npm run build` (chunk inspection + size diff) for frontend; full `pytest -q` + golden for CLI.
- **Before verify:** vitest green, `npm run build` succeeds with per-page chunks + separate `@imgly` chunk + smaller entry; `pytest -q` green; golden cli byte-identical; CLI subprocess import check passes; before/after sizes + importtime recorded.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 5-lazy-routes | 01 | 1 | WEB-01 | N/A | unit + build | `cd web && npm run test`; `npm run build` (per-page chunks) | ✅ App.test + ❌ build inspect | ⬜ pending |
| 5-deaddep-imgly | 01 | 1 | WEB-02 | smaller supply-chain surface | build + grep | `grep -rn html-to-image src` (none); `npm run build` (@imgly own chunk) | ✅ grep + ❌ build inspect | ⬜ pending |
| 5-query-tuning | 01 | 1 | WEB-03 | N/A | unit | `cd web && npm run test` (App.test + page tests green) | ✅ vitest | ⬜ pending |
| 5-cli-defer | 02 | 1 | CLI-01 | N/A | unit + import-cost | `pytest tests/test_cli.py tests/test_cli_startup.py -q`; golden cli | ✅ test_cli/golden + ❌ W0 startup test | ⬜ pending |
| 5-regress | all | all | (all) | N/A | regression | `pytest -q` + `npm run test` + golden | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cli_startup.py` — subprocess assertion that `import fc26.cli` does NOT pull `selectolax` or `httpx` into `sys.modules` (proves CLI-01 deferral); fast, default-suite (no marker).
- [ ] No new web unit test needed — `App.test.tsx` (routes via async `findBy*`) + per-page `*.test.tsx` already cover render/route under lazy. The bundle before/after size is recorded in the summary from `npm run build` (no golden — bytes change by design).
- [ ] No new golden — CLI text is already goldened (`cli_list`/`cli_show`) and must stay byte-identical; regenerate ONLY if an intended change occurs (there must be none).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Initial JS bundle materially smaller; `@imgly` not in entry | WEB-01/02 | bundle-size is a build artifact, not a unit assertion | `cd web && npm run build`; compare entry-chunk size before/after (research baseline ~298 KB); confirm a separate `@imgly` chunk reachable only from the generator page |
| Real navigation doesn't refetch static data | WEB-03 | network timing in a live browser | Optional: `fc26 serve`, open devtools Network, navigate between pages, confirm `/api/meta` not re-fired within the staleTime window |
| Playwright e2e under lazy routes | WEB-01 | needs a running `fc26 serve` | `cd web && npm run e2e` (specs wait on content, resilient to the Suspense fallback) |
| `--help` startup faster | CLI-01 | wall-clock startup | `python -X importtime -m fc26 --help 2>&1 \| sort -k2 -rn \| head` before/after; record in summary |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers MISSING references (test_cli_startup)
- [ ] No watch-mode flags (use `npm run test` = `vitest run`, not `test:watch`)
- [ ] CLI golden byte-identical after the deferral change
- [ ] `npm run build` succeeds; entry shrinks; per-page + separate @imgly chunks present
- [ ] `nyquist_compliant: true` set once tasks map cleanly

**Approval:** pending
