# FC 26 Player DB — Design Spec (Phase 1)

**Date:** 2026-06-10
**Status:** Approved by user
**Project:** footie — FC 26 Playbook (PS5)

## Context

The repo today is a markdown playbook with crawled stat tables (fcratings.com top-100
base cards in `docs/08`, pace lists in `docs/09`/`docs/10`, fut.gg special cards in
`docs/11`). The long-term goal is a program that collects FC 26 (PS5) player stats and
assists with squads, skills, strategy, acquisitions, lineups, and formations.

Decisions made during brainstorming:

- **Architecture:** data engine + CLI first; web UI later (option C).
- **Data collection:** hybrid — one-time seed from existing crawled data, incremental
  paste-URL crawl for special cards, re-crawl on demand (option C).
- **Mode focus:** FUT (Ultimate Team) only. Chemistry matters; Career Mode does not.
- **Build order:** Player DB first (option A). Chemistry engine, squad builder,
  acquisition planner, and strategy advisor are separate, later specs.
- **Stack:** Python engine + CLI core; future web is a TS frontend talking to a
  Python API (option C).

## Sub-project decomposition (roadmap)

1. **Player DB** ← this spec
2. Chemistry engine — FC26 FUT chem (per-player 0–3, league/nation/club thresholds,
   position match, chem styles)
3. Squad/lineup builder — formation slots, role assignment, chem-optimized XI
4. Acquisition planner — gap analysis, PlayStyle+ targets, upgrade suggestions
5. Strategy advisor — formation/tactics recommender wrapping the existing docs
6. Web UI / API server

Each later sub-project gets its own spec → plan → implementation cycle.

## Phase 1 scope

A Python package `fc26` providing an immutable player-card data model, a JSON
repository, three ingest paths, and a Typer CLI.

```
fc26/
  models.py        # Player/Card frozen dataclasses (immutable)
  db.py            # repository: load/save/search JSON store
  ingest/
    futgg.py       # parse fut.gg per-card page → Card
    fcratings.py   # parse fcratings top-100 list → base Cards
    seed.py        # one-time: existing docs/*.md tables → JSON
  cli.py           # Typer entry point
data/
  players.json     # the DB (committed, human-diffable)
```

Key choices:

- **Card is the unit of data.** One player has many cards (base, TOTS, PTG, …).
- **DB is a JSON file committed to git** — diffable, no server; the future web phase
  reads the same file via an API.
- **Repository pattern** with `findAll`/`findById`/`search`/`upsert`; models are
  immutable (frozen dataclasses); updates return new objects.
- **Chemistry fields (club/league/nation) are captured now** so the chemistry engine
  (sub-project 2) requires no schema change.

## Data model

```python
# models.py — all frozen dataclasses

FaceStats:   pac, sho, pas, dri, def_, phy          # ints 1-99
SubStats:    acceleration, sprint_speed, positioning, finishing,
             shot_power, long_shots, volleys, penalties, vision,
             crossing, fk_accuracy, short_passing, long_passing, curve,
             agility, balance, reactions, ball_control, dribbling,
             composure, interceptions, heading_accuracy, def_awareness,
             standing_tackle, sliding_tackle, jumping, stamina,
             strength, aggression                    # Optional — fut.gg has, fcratings doesn't

Card:
  id: str                       # slug: "ronaldo-tots", "rodri-base"
  player_name: str
  version: str                  # "base" | "TOTS" | "PTG" | ...
  ovr: int
  position: str                 # primary, e.g. "ST"
  alt_positions: tuple[str, ...]
  face: FaceStats
  subs: SubStats | None
  playstyles: tuple[str, ...]
  playstyles_plus: tuple[str, ...]
  accelerate: str | None        # "Explosive" | "Controlled" | ...
  skill_moves: int | None       # 1-5
  weak_foot: int | None         # 1-5
  club: str | None
  league: str | None            # chem fields — nullable, source-dependent
  nation: str | None
  height_cm: int | None
  age: int | None
  price: int | None             # coins; manual/optional in phase 1
  source_url: str | None
  crawled_at: str | None        # ISO date
```

- **Nullable-heavy by design:** fcratings provides rank/OVR/pos/club only; fut.gg
  provides everything. Seed fills what exists; `fc26 add <url>` enriches.
- `id` is deterministic from name + version, so upsert replaces in place — no dupes.
- **Validation at the boundary:** parser output is validated before any write — OVR
  1–99, position in a known set, stats in range. A bad page produces a clear error
  and never a partial write.
- `players.json` shape: `{"schema_version": 1, "cards": [...]}` — versioned for
  future migrations.

## Ingest paths

1. **`fc26 seed`** — one-time. Parses the existing markdown tables (`docs/08` top-100,
   `docs/09`/`docs/10` pace lists, `docs/11` special cards) into `players.json`.
   Markdown tables are already structured, so this is a regex/split parse. Idempotent:
   re-running produces the same result.
2. **`fc26 add <fut.gg url>`** — fetches a per-card page (server-rendered; the
   existing `docs/11` workflow proves it crawls cleanly) and parses full stats,
   PlayStyles, AcceleRATE, club/league/nation. Uses httpx + selectolax. Replaces the
   manual paste-into-markdown workflow.
3. **`fc26 sync`** — re-crawls the fcratings top-100 list. New or changed base cards
   are upserted. **Merge rule:** never overwrite richer fut.gg data with poorer
   fcratings data — fut.gg-sourced fields win unless null.

## Error handling

- **Network:** 15s timeout, 1 retry, then a clean error including the URL. No
  partial writes.
- **Parse:** a selector miss raises `ParseError` naming the missing field and URL
  (hint: "fut.gg layout changed?"). Validation reports all failures at once, not
  just the first.
- **Write:** serialize to a temp file, then atomic rename. The DB can never be
  corrupted by an interrupted write.
- **Polite crawling:** 1 request/second delay during sync, honest User-Agent.

## CLI surface

```
fc26 seed                      # docs/*.md → data/players.json (one-time)
fc26 add <fut.gg-url>          # crawl one card, upsert
fc26 sync                      # re-crawl fcratings top-100, merge
fc26 search <text>             # name/club/version match → table
fc26 show <id|name>            # full card detail (all stats, PlayStyles)
fc26 list --pos ST --sort pac  # filter/sort: pos, ovr, pac, version, league…
```

- Terminal output uses rich tables.
- `--json` flag on `search`/`list`/`show` emits machine-readable output (for the
  web phase and scripting).

## Testing

- Saved HTML fixtures (one fut.gg card page, one fcratings list page) make parser
  tests offline and deterministic.
- Repository unit tests (load/save/search/upsert/merge rules).
- A live-crawl test exists but is opt-in (marked, skipped by default).
- Target: 80%+ coverage (unit + integration; no UI yet, so no E2E in phase 1).

## Explicitly out of scope for phase 1 (YAGNI)

- Chemistry engine (sub-project 2)
- Squad/lineup/formation builder (3)
- Acquisition planner and price tracking (4)
- Strategy advisor (5)
- Web UI / API server (6)
- Auto-updating `docs/*.md` from the DB — after seeding, the DB is the source of
  truth for data; the docs remain the written guide.

## Stack

Python 3.12+, httpx, selectolax, Typer, rich, pytest. Packaged with
`pyproject.toml`; installed for development with `pip install -e .`.
