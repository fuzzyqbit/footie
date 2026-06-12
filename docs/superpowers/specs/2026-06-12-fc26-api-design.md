# FC 26 API Server (`fc26 serve`) — Design Spec (Phase 8A)

**Date:** 2026-06-12
**Status:** Approved by user
**Depends on:** Phases 1–7 (full engine: repo, chem, boost, upgrade, build)

## Decisions (user-approved)

- Web UI split into two specs: **8A = FastAPI server** (this spec), **8B = Vite/React
  TS frontend** (separate spec, later). v1 frontend ambition = dashboard (read +
  run); drag-drop pitch editing is a later phase (option C).
- Stack per the phase-0 decision: Python core exposes JSON; TS frontend consumes it.
- Execution note: this phase should be implemented in a FRESH session (this one is
  near its context limit). Spec + plan + memory carry the state.

## Architecture

```
fc26/api/__init__.py
fc26/api/app.py          # create_app(db_path, squads_dir) -> FastAPI; routes are
                         # thin JSON adapters over existing pure functions
fc26/cli.py              # new: fc26 serve [--port 8026] [--db ...] (uvicorn, 127.0.0.1)
```

No business logic in routes. Every route resolves to an existing function:
CardRepository, compute_chemistry, boosted_stats, find_upgrades, build_squad,
load_lineup/resolve_cards, FORMATIONS, available_styles.

## Endpoints

All responses use the envelope `{"ok": bool, "data": ..., "error": str | null}`.
FC26Error (any subclass) → HTTP 400 with the error message in the envelope;
unknown id/file → 404; unexpected exceptions → 500 with a generic message (no
traceback leakage).

```
GET  /api/cards            ?search=&pos=&version=&league=&min_ovr=&sort=ovr|pac|name&limit=50&offset=0
                           -> {total, cards: [card dicts]}   (paginated; filters mirror `fc26 list` +
                              search semantics of `fc26 search`; league filter alias-aware)
GET  /api/cards/{id}       -> card dict
GET  /api/squads           -> [{name, path}] from squads/*.json
GET  /api/squads/{name}    -> squad file JSON (name = stem, path-traversal rejected)
PUT  /api/squads/{name}    -> validate body via load_lineup semantics (write to temp
                              file then load, or refactor a validate_squad_dict helper);
                              on success write squads/{name}.json; invalid -> 400 listing
                              ALL errors (house style)
POST /api/chem             body: squad JSON (inline, same shape as files) -> ChemReport (asdict)
POST /api/boost            body: squad JSON -> {players: [BoostResult dicts...], team_chem}
POST /api/upgrade          body: {squad: {...}, budget: "100K", swaps: 3} -> UpgradePlan (asdict)
POST /api/build            body: {formation, budget: "500K", league?} -> {formation, seed_cost,
                              total_cost, team_chem, xi: [...], squad: {standard squad-file shape}}
GET  /api/meta             -> {formations: {...}, styles: [...], leagues: [distinct canonical
                              display names from DB], versions: [distinct]}
```

- Inline squad bodies let the UI compute chem/boost/upgrade without saving files.
- `POST /api/build` returns the squad in file shape so the UI can offer "save"
  via `PUT /api/squads/{name}`.
- Squad PUT must never escape `squads/` (reject names with path separators or
  `..`; slugify the name).

## Server behavior

- `fc26 serve [--port 8026] [--db data/players.json]` — binds 127.0.0.1 ONLY
  (single-user local tool, no auth by design; not for exposure).
- CORS: allow `http://localhost:5173` (Vite dev) only.
- DB is read per request via the existing repository (file-backed; no caching
  layer — n=2.4k loads in ms; revisit only if profiling demands).
- New deps: `fastapi`, `uvicorn` (pyproject `[project.dependencies]`).

## Testing

- FastAPI TestClient suite against a tmp DB (fixtures mirroring the CLI tests):
  every endpoint happy path + error paths (unknown card 404, invalid squad 400
  with all errors listed, bad budget 400, unknown formation 400, path-traversal
  PUT rejected, envelope shape everywhere).
- Real-DB CI guards (skippable like existing ones): /api/cards pagination over
  2,4xx cards; POST /api/chem with the sample squad returns team_total 33.
- Coverage ≥80%; existing suite untouched and green.

## Non-goals (8B and later)

- The frontend itself (spec 8B: Vite/React/TS in `web/`, pages Cards/Squad/Build/
  Upgrade, vertical pitch via formation slots, dropdown slot pickers; `fc26 serve`
  later gains static serving of `web/dist`; drag-drop after 8B)
- Auth, HTTPS, multi-user, remote exposure
- Live price refresh endpoints (run `fc26 expand` out-of-band)
- WebSockets/live recompute

## Success criteria

- `fc26 serve` + `curl localhost:8026/api/cards?search=mbappe` round-trips.
- POST /api/chem on the committed sample squad returns 33/33 via HTTP.
- All FC26Error paths surface as clean 400 envelopes, never tracebacks.
