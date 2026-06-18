# footie — Performance & Speed Milestone

## What This Is

footie is an FC 26 (PS5) FUT player database + squad assistant: it scrapes card data (fut.gg, fcratings, futbin), stores it in a JSON database, computes squad chemistry/builds, and serves a React/Vite web app + typer CLI over a FastAPI backend. This milestone makes the existing program **faster** — refresh, API, and web load — **without changing what it produces**.

## Core Value

footie stays byte-for-byte correct (same data, same API responses, same CLI output, tests green) but runs noticeably faster across scraping, backend, and web. Speed only — zero behavior change.

## Requirements

### Validated

<!-- Inferred from existing code (.planning/codebase/). These already work and are relied upon. -->

- ✓ Scrape FC26 card data from fut.gg / fcratings / futbin (`fc26/ingest`) — existing
- ✓ JSON player database (`fc26/db.py`, `data/players.json`, ~2,434 cards) — existing
- ✓ Squad builder + chemistry engine (`fc26/builder`, `fc26/chem`) — existing
- ✓ FastAPI backend + React/Vite web app (cards, squad, planner, advisor, objectives, SBCs) — existing
- ✓ typer CLI (`build`, `serve`, `refresh`, `search`, …) — existing
- ✓ Test suites: pytest (offline + opt-in live), vitest, Playwright e2e — existing

### Active

<!-- This milestone. All are speed improvements; none may change observable output. -->

- [ ] In-memory cache over the JSON store — load once, index by id; eliminate per-request full re-parse
- [ ] Batch/atomic writes — kill the O(n²) per-card whole-file rewrite during refresh
- [ ] Async scraper rewrite — `httpx.AsyncClient` + `asyncio.gather`, bounded concurrency, connection reuse, polite throttle preserved
- [ ] Faster API — keep blocking compute off the event loop; memoize chemistry in build/upgrade; cache static `/api/meta`
- [ ] Web app load — route code-splitting (`React.lazy`), tune React Query cache, lazy heavy deps
- [ ] CLI startup — lazy imports so `--help`/simple commands don't load the whole graph
- [ ] Benchmark/profiling harness — establish baselines (none exist today) to prove speedups and guard against regressions

### Out of Scope

- **SQLite migration** — keep dad's JSON format; an in-process cache solves the read cost at this scale. Documented as a possible future phase, not this milestone.
- **Redis / Memcached / RabbitMQ** — single-process, single-node, single-user; an in-process dict is faster than an out-of-process cache here, and a broker solves a distribution problem that doesn't exist. (Analyzed 2026-06-17.)
- **Behavior / output changes** — outputs (JSON format, API responses, CLI text) must stay identical.
- **New features** — this milestone is performance only.

## Context

- **Brownfield.** Codebase mapped first — see `.planning/codebase/` (STACK, ARCHITECTURE, QUALITY, CONCERNS).
- **Root cause** of most slowness: `data/players.json` (~4.4 MB / 2,434 cards) is fully re-read + re-parsed on nearly every operation, and rewritten whole on every `upsert` (`fc26/db.py`). This single fact drives the refresh O(n²) and per-request re-parse costs.
- **Other hot paths:** sequential throttled HTTP with no connection reuse (`fc26/ingest`); blocking compute inside `async def` handlers + heavy chem recompute in build/upgrade (`fc26/api/app.py`, `fc26/builder`); un-split ~298 KB web bundle (`web/`).
- **Safety net:** strong behavioral tests (offline pytest + vitest + e2e), but **no latency/throughput benchmark** exists — a profiling harness must be added so speedups are measurable and behavior-equivalence is enforced.

## Constraints

- **Behavior**: Outputs must stay identical — same `data/players.json` format, same API responses, same CLI output. All existing tests must stay green. — *dad's authoritative tool; correctness is non-negotiable.*
- **Ownership / Branching**: `main` is dad's authoritative branch (read-only); all work lands on `ro`. Do not change the on-disk data format. — *per CLAUDE.md HARD RULE.*
- **Politeness**: Async scrapers must keep rate-limiting / bounded concurrency / throttle to external sites (fut.gg, fcratings, futbin). — *don't get the source IPs blocked.*
- **No new infra**: No external servers (Redis/Memcached/RabbitMQ). Wins must be in-process + algorithmic. — *single-process scale; infra adds latency + ops.*

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| In-memory cache over JSON, keep file format | In-proc dict is faster than Redis at single-process scale and preserves dad's format | — Pending |
| Async ingest rewrite (`AsyncClient` + `gather`) | Sequential sleeps dominate refresh time; bounded async maximizes throughput while staying polite | — Pending |
| No Redis / Memcached / RabbitMQ | Single-process/single-node; out-of-process cache adds latency, broker solves a non-existent distribution problem | ✓ Good (analyzed) |
| Zero behavior change; add benchmark harness | dad's authoritative tool — prove speed without altering output; baselines guard regressions | — Pending |
| Defer SQLite to a future phase | Cache captures most of the read win now without rewriting the data layer dad authored | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-17 after initialization*
