"""FastAPI app factory for fc26 serve."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..builder.boost import boosted_stats
from ..builder.build import build_squad
from ..builder.market import parse_budget
from ..builder.upgrade import find_upgrades
from ..chem.aliases import canonical_league
from ..chem.engine import compute_chemistry
from ..chem.formations import FORMATIONS
from ..chem.lineup import lineup_from_dict, resolve_cards
from ..chem.styles import available_styles
from ..db import CardRepository, card_to_dict
from ..errors import FC26Error
from ..ingest.refresh import (
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_MIN_OVR,
    jittered_sleep,
    refresh_data,
)
from ..ingest.web import fetch_html

_log = logging.getLogger("fc26.refresh")

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

_SORT_KEYS = {
    "ovr": lambda c: c.ovr,
    "pac": lambda c: c.face.pac or 0,
    "name": lambda c: c.player_name.lower(),
}


def _ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None}


def _err(msg: str) -> dict:
    return {"ok": False, "data": None, "error": msg}


def _safe_stem(name: str) -> str | None:
    """Return name if safe for use as a squad file stem, else None."""
    if not name or not _SAFE_NAME_RE.match(name):
        return None
    return name


async def _refresh_loop(db_path: Path, interval_hours: float, min_ovr: int) -> None:
    """Re-scrape the live pool every `interval_hours` while the server runs.

    Runs the blocking scrape in a worker thread so request handling is never
    stalled. Any failure (network, futbin layout change) is logged and the loop
    keeps going; the on-disk db is left untouched on a hard failure because
    upsert merges rather than truncating.
    """
    interval = max(interval_hours, 0.0) * 3600
    while True:
        await asyncio.sleep(interval)
        _log.info("auto-refresh starting (min_ovr=%s)", min_ovr)
        try:
            repo = CardRepository(db_path)
            result = await asyncio.to_thread(
                refresh_data, repo,
                min_ovr=min_ovr, fetch_html=fetch_html, sleep=jittered_sleep,
            )
            _log.info(
                "auto-refresh done: %s new, %s updated, %s enriched",
                result.expand.new, result.expand.merged, len(result.enrich.enriched),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("auto-refresh failed; keeping existing data")


def create_app(
    db_path: Path,
    squads_dir: Path,
    web_dir: Path | None = None,
    *,
    auto_refresh: bool = False,
    refresh_interval_hours: float = DEFAULT_INTERVAL_HOURS,
    refresh_min_ovr: int = DEFAULT_MIN_OVR,
) -> FastAPI:
    @contextlib.asynccontextmanager
    async def _lifespan(_app: FastAPI):
        task: asyncio.Task | None = None
        if auto_refresh:
            task = asyncio.create_task(
                _refresh_loop(db_path, refresh_interval_hours, refresh_min_ovr)
            )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="FC 26 API", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(FC26Error)
    async def _fc26_error(request: Request, exc: FC26Error) -> JSONResponse:
        return JSONResponse(status_code=400, content=_err(str(exc)))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_err(exc.detail))

    @app.exception_handler(Exception)
    async def _generic_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=_err("internal server error"))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        msg = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        return JSONResponse(status_code=422, content=_err(msg))

    @app.get("/api/cards")
    async def list_cards(
        search: str | None = None,
        pos: str | None = None,
        version: str | None = None,
        league: str | None = None,
        min_ovr: int | None = None,
        sort: str = "ovr",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if sort not in _SORT_KEYS:
            raise FC26Error(f"unknown sort key {sort!r} (use: ovr, pac, name)")
        if limit < 1:
            raise FC26Error("limit must be >= 1")
        if offset < 0:
            raise FC26Error("offset must be >= 0")
        repo = CardRepository(db_path)
        cards = list(repo.search(search) if search else repo.find_all())
        if pos:
            wanted = pos.upper()
            cards = [c for c in cards if c.position == wanted or wanted in c.alt_positions]
        if version:
            cards = [c for c in cards if c.version.lower() == version.lower()]
        if league:
            wanted_lg = canonical_league(league)
            cards = [c for c in cards
                     if c.league is not None and canonical_league(c.league) == wanted_lg]
        if min_ovr is not None:
            cards = [c for c in cards if c.ovr >= min_ovr]
        reverse = sort != "name"
        cards.sort(key=_SORT_KEYS[sort], reverse=reverse)
        total = len(cards)
        return _ok({"total": total, "cards": [card_to_dict(c) for c in cards[offset:offset + limit]]})

    @app.get("/api/cards/{card_id}")
    async def get_card(card_id: str) -> dict:
        card = CardRepository(db_path).find_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"card {card_id!r} not found")
        return _ok(card_to_dict(card))

    @app.get("/api/squads")
    async def list_squads() -> dict:
        files = sorted(squads_dir.glob("*.json"))
        return _ok([{"name": f.stem, "path": str(f)} for f in files])

    @app.get("/api/squads/{name}")
    async def get_squad(name: str) -> dict:
        stem = _safe_stem(name)
        if stem is None:
            raise HTTPException(status_code=400, detail=f"invalid squad name {name!r}")
        path = squads_dir / f"{stem}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"squad {name!r} not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"cannot read squad: {exc}") from exc
        return _ok(data)

    @app.put("/api/squads/{name}")
    async def put_squad(name: str, request: Request) -> dict:
        stem = _safe_stem(name)
        if stem is None:
            raise HTTPException(status_code=400, detail=f"invalid squad name {name!r}")
        body = await request.json()
        lineup_from_dict(body, name=stem)   # raises LineupError (-> 400) if invalid
        path = squads_dir / f"{stem}.json"
        path.write_text(json.dumps(body, indent=2), encoding="utf-8")
        return _ok({"name": stem, "path": str(path)})

    @app.post("/api/chem")
    async def post_chem(request: Request) -> dict:
        body = await request.json()
        lineup = lineup_from_dict(body)
        repo = CardRepository(db_path)
        slot_cards = resolve_cards(lineup, repo)
        report = compute_chemistry(lineup, slot_cards)
        return _ok(asdict(report))

    @app.post("/api/boost")
    async def post_boost(request: Request) -> dict:
        body = await request.json()
        lineup = lineup_from_dict(body)
        repo = CardRepository(db_path)
        slot_cards = resolve_cards(lineup, repo)
        report = compute_chemistry(lineup, slot_cards)
        chem_by_slot = {p.slot: p.chem for p in report.players}
        results = [
            asdict(boosted_stats(card, lineup.styles.get(slot), chem_by_slot.get(slot, 0)))
            for slot, card in slot_cards.items()
        ]
        return _ok({"players": results, "team_chem": report.team_total})

    @app.post("/api/upgrade")
    async def post_upgrade(request: Request) -> dict:
        body = await request.json()
        squad_data = body.get("squad") or {}
        budget_str = str(body.get("budget", "0"))
        swaps = int(body.get("swaps", 3))
        lineup = lineup_from_dict(squad_data)
        repo = CardRepository(db_path)
        slot_cards = resolve_cards(lineup, repo)
        budget = parse_budget(budget_str)
        pool = repo.find_all()
        plan = find_upgrades(lineup, slot_cards, pool, budget=budget, max_swaps=swaps)
        return _ok(asdict(plan))

    @app.post("/api/build")
    async def post_build(request: Request) -> dict:
        body = await request.json()
        formation = str(body.get("formation", ""))
        budget_str = str(body.get("budget", "0"))
        league = body.get("league")
        objective = str(body.get("objective", "meta"))
        budget = parse_budget(budget_str)
        repo = CardRepository(db_path)
        pool = repo.find_all()
        result = build_squad(formation, pool, budget=budget, league=league, objective=objective)
        report = compute_chemistry(result.lineup, result.slot_cards)
        squad_dict: dict = {
            "name": result.lineup.name or "built-squad",
            "formation": result.lineup.formation,
            "starting_xi": {slot: card.id for slot, card in result.slot_cards.items()},
        }
        if result.lineup.manager:
            squad_dict["manager"] = {
                "league": result.lineup.manager.league,
                "nation": result.lineup.manager.nation,
            }
        xi = [
            {"slot": slot, **card_to_dict(card)}
            for slot, card in result.slot_cards.items()
        ]
        return _ok({
            "formation": result.lineup.formation,
            "seed_cost": result.seed_cost,
            "total_cost": result.total_cost,
            "team_chem": report.team_total,
            "xi": xi,
            "squad": squad_dict,
        })

    @app.get("/api/meta")
    async def get_meta() -> dict:
        repo = CardRepository(db_path)
        all_cards = repo.find_all()
        leagues = sorted({c.league for c in all_cards if c.league})
        versions = sorted({c.version for c in all_cards})
        return _ok({
            "formations": {name: list(slots) for name, slots in FORMATIONS.items()},
            "styles": list(available_styles()),
            "leagues": leagues,
            "versions": versions,
        })

    # Serve the built SPA (web/dist) as a single-page app. Registered AFTER the
    # /api routes so those match first; unmatched /api/* stays a JSON 404. Any
    # other unknown path falls back to index.html for client-side routing.
    if web_dir is not None and (web_dir / "index.html").is_file():
        root = web_dir.resolve()
        index_html = root / "index.html"

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail=f"{full_path!r} not found")
            candidate = (root / full_path).resolve()
            if candidate.is_file() and root in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index_html)

    return app
