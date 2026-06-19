# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-17)

**Core value:** footie stays byte-for-byte correct (same data, API responses, CLI output, tests green) but runs noticeably faster across scraping, backend, and web — speed only, zero behavior change.
**Current focus:** Phase 1 — Benchmark & Equivalence Harness

## Current Position

Phase: 5 of 5 (Frontend Load & CLI Startup) — PLANNED ✓ (ready to execute)
Plan: 0 of 2 executed (2 plans written + checker PASS)
Status: Phase 5 planned — 05-01 (frontend: React.lazy routes + Suspense, remove dead html-to-image, vendor chunk split, React Query tuning), 05-02 (CLI deferred imports + light constants module). Sonnet plan-checker PASS (1 blocker + 2 warnings raised then resolved). Ready for `/gsd:execute-phase 5` (final phase). Phases 1-4 COMPLETE ✓.
Last activity: 2026-06-19 — Phase 5 planned (RESEARCH anchors FRONTEND-TOOLING §A/§B4; key trap caught: DEFAULT_* option defaults must move to a light fc26/ingest/constants.py or they drag selectolax/httpx into CLI import; CLI test monkeypatch targets retargeted to source modules)

Progress: [████████░░] 80% (4 of 5 phases complete; Phase 5 planned)

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
Stopped at: Phase 5 planned (2 plans + checker PASS); merged to ro.
Resume file: None
Next action: `/gsd:execute-phase 5` (final phase — Frontend Load & CLI Startup)
