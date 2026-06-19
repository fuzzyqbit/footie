# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-17)

**Core value:** footie stays byte-for-byte correct (same data, API responses, CLI output, tests green) but runs noticeably faster across scraping, backend, and web — speed only, zero behavior change.
**Current focus:** Phase 1 — Benchmark & Equivalence Harness

## Current Position

Phase: 5 of 5 (Frontend Load & CLI Startup) — COMPLETE ✓
Plan: 2 of 2 executed
Status: 🎉 MILESTONE COMPLETE — all 5 phases done, all 18 v1 requirements delivered, byte-identical. Phase 5 verified PASSED (frontend code-split: entry 336→189 kB, pages + @imgly lazy; CLI import 416→273 modules, selectolax/httpx no longer loaded).
Last activity: 2026-06-19 — Phase 5 executed (React.lazy routes + Suspense + vendor split + html-to-image removed + React Query tuning; CLI heavy-import deferral + light constants module; vitest 72, golden byte-identical, full suite 365 green)

Progress: [██████████] 100% (5 of 5 phases complete) ✓

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Milestone]: In-memory cache over JSON, keep dad's file format (in-proc dict beats Redis at single-process scale).
- [Milestone]: Async ingest rewrite (`AsyncClient` + `gather`) — bounded + polite, sequential sleeps dominate refresh.
- [Milestone]: No Redis/Memcached/RabbitMQ; no SQLite (deferred). In-process + algorithmic wins only.
- [Milestone]: Zero behavior change; add benchmark + golden-equivalence harness first — baselines guard regressions.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- No profiling data exists yet — all bottleneck rankings are structural; Phase 1 harness must capture baselines on `ro` HEAD before any optimization ships.
- Output-equivalence traps to guard in the harness: single serial writer (concurrent upsert corruption), `expand` id-suffix order dependence, `/api/meta` version-filter falsy quirk, tier-point step functions (why algorithmic chemistry stays v2/gated).
- Branching: `main` is dad's authoritative branch; all work lands on `ro` (per CLAUDE.md).

## Deferred Items

Items acknowledged and carried forward (v2 — gated behind the equivalence harness, only if profiling still warrants):

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| CHEM | CHEM-01 cheaper `compute_chemistry` via precomputed facts | Deferred (v2) | 2026-06-17 |
| CHEM | CHEM-02 incremental chemistry delta / admissible pruning (high risk) | Deferred (v2) | 2026-06-17 |
| STORE | STORE-01 optional SQLite migration of the player store | Deferred (v2) | 2026-06-17 |

## Session Continuity

Last session: 2026-06-19
Stopped at: 🎉 Milestone complete — Phase 5 executed + verified PASSED; merged to ro. All 5 phases shipped.
Resume file: None
Next action: Milestone done. Optional follow-ups: run e2e/web on a serve env; capture final before/after numbers on a quiet machine; consider v2 (CHEM-01/02, STORE-01) only if profiling still warrants.
