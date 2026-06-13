"""FastAPI app factory for fc26 serve."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


def create_app(db_path: Path, squads_dir: Path) -> FastAPI:
    app = FastAPI(title="FC 26 API")

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

    return app
