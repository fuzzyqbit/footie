"""fc26 command-line interface."""

from __future__ import annotations

import json as json_lib
import time
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

from .db import CardRepository, card_to_dict
from .errors import FC26Error
from .ingest.enrich import enrich_cards
from .ingest.expand import expand_cards
from .ingest.fcratings import fetch_top100
from .ingest.futgg import fetch_futgg_card
from .ingest.seed import seed_cards
from .ingest.web import fetch_html
from .models import Card

app = typer.Typer(help="FC 26 (PS5) FUT player database", no_args_is_help=True)
console = Console(width=200)

DEFAULT_DB = Path("data/players.json")
DB_OPTION = typer.Option(DEFAULT_DB, "--db", help="Path to players.json")
JSON_FLAG = typer.Option(False, "--json", help="Emit JSON instead of a table")


def _fail(message: str) -> NoReturn:
    console.print(f"[red]error:[/red] {message}")
    raise typer.Exit(code=1)


def _print_cards(cards: tuple[Card, ...] | list[Card], as_json: bool) -> None:
    if as_json:
        typer.echo(json_lib.dumps([card_to_dict(c) for c in cards], ensure_ascii=False, indent=2))
        return
    table = Table("ID", "Player", "Version", "OVR", "Pos", "PAC", "Club")
    for card in cards:
        table.add_row(
            card.id, card.player_name, card.version, str(card.ovr),
            card.position, str(card.face.pac or "-"), card.club or "-",
        )
    console.print(table)


@app.command()
def seed(
    docs_dir: Path = typer.Option(Path("docs"), "--docs-dir", help="Directory holding docs 08/10/11"),
    db: Path = DB_OPTION,
) -> None:
    """One-time: build the DB from this repo's crawled markdown docs."""
    try:
        top100_md = (docs_dir / "08-player-ratings-top100.md").read_text(encoding="utf-8")
        master_md = (docs_dir / "10-fastest-xi.md").read_text(encoding="utf-8")
        specials_md = (docs_dir / "11-special-cards.md").read_text(encoding="utf-8")
    except OSError as exc:
        _fail(f"cannot read seed docs: {exc}")
    repo = CardRepository(db)
    cards = seed_cards(top100_md, master_md, specials_md)
    # no transaction needed: upsert is idempotent, so a mid-loop failure
    # leaves a partial-but-consistent DB and re-running seed completes it
    try:
        for card in cards:
            repo.upsert(card)
    except FC26Error as exc:
        _fail(f"seed aborted: {exc}")
    console.print(f"seeded {len(cards)} card records → {len(repo.find_all())} unique cards in {db}")


@app.command()
def add(url: str, db: Path = DB_OPTION) -> None:
    """Crawl one fut.gg per-card page and upsert it."""
    try:
        card = fetch_futgg_card(url)
        merged = CardRepository(db).upsert(card)
    except FC26Error as exc:
        _fail(str(exc))
    console.print(f"added [bold]{merged.player_name}[/bold] ({merged.version}) as {merged.id}")


@app.command()
def sync(db: Path = DB_OPTION) -> None:
    """Re-crawl the fcratings top-100 and merge (fut.gg data is never degraded)."""
    try:
        cards = fetch_top100()
    except FC26Error as exc:
        _fail(str(exc))
    repo = CardRepository(db)
    for card in cards:
        repo.upsert(card)
    console.print(f"synced {len(cards)} base cards into {db}")


@app.command()
def search(text: str, db: Path = DB_OPTION, json: bool = JSON_FLAG) -> None:
    """Find cards by name, club, or version (case-insensitive)."""
    try:
        cards = CardRepository(db).search(text)
    except FC26Error as exc:
        _fail(str(exc))
    if not cards:
        _fail(f"no cards match {text!r}")
    _print_cards(cards, json)


@app.command()
def show(ident: str, db: Path = DB_OPTION, json: bool = JSON_FLAG) -> None:
    """Show one card in full detail, by id or name."""
    try:
        repo = CardRepository(db)
        card = repo.find_by_id(ident)
        if card is None:
            matches = [c for c in repo.find_all() if c.player_name.lower() == ident.lower()]
            if len(matches) == 1:
                card = matches[0]
            elif matches:
                _print_cards(matches, as_json=False)
                _fail(f"{ident!r} is ambiguous - use an id from the list above")
    except FC26Error as exc:
        _fail(str(exc))
    if card is None:
        _fail(f"no card found for {ident!r}")
    if json:
        typer.echo(json_lib.dumps(card_to_dict(card), ensure_ascii=False, indent=2))
        return
    console.print(card_to_dict(card))


SORT_KEYS = {
    "ovr": lambda c: c.ovr,
    "pac": lambda c: c.face.pac or 0,
    "name": lambda c: c.player_name.lower(),
}


@app.command(name="list")
def list_cards(
    pos: str | None = typer.Option(None, "--pos", help="Filter by primary or alt position"),
    version: str | None = typer.Option(None, "--version", help="Filter by card version"),
    league: str | None = typer.Option(None, "--league", help="Filter by league (substring)"),
    sort: str = typer.Option("ovr", "--sort", help="ovr | pac | name"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """List cards with filters and sorting."""
    if sort not in SORT_KEYS:
        _fail(f"unknown sort key {sort!r} (use: {', '.join(SORT_KEYS)})")
    try:
        cards = list(CardRepository(db).find_all())
    except FC26Error as exc:
        _fail(str(exc))
    if pos:
        wanted = pos.upper()
        cards = [c for c in cards if c.position == wanted or wanted in c.alt_positions]
    if version:
        cards = [c for c in cards if c.version.lower() == version.lower()]
    if league:
        cards = [c for c in cards if league.lower() in (c.league or "").lower()]
    reverse = sort != "name"
    cards.sort(key=SORT_KEYS[sort], reverse=reverse)
    _print_cards(cards, json)


@app.command()
def enrich(
    refresh: bool = typer.Option(False, "--refresh", help="Re-fetch even already-enriched cards"),
    limit: int | None = typer.Option(None, "--limit", help="Cap player-page fetches"),
    db: Path = DB_OPTION,
) -> None:
    """Bulk-fill league/nation/face stats from fcratings player pages."""
    repo = CardRepository(db)
    try:
        result = enrich_cards(
            repo,
            fetch_html=fetch_html,
            sleep=time.sleep,
            on_progress=console.print,
            refresh=refresh,
            limit=limit,
        )
    except FC26Error as exc:
        _fail(str(exc))
    console.print(
        f"enriched {len(result.enriched)}, skipped {len(result.skipped)}, "
        f"missed {len(result.missed)}"
    )
    for miss in result.missed:
        console.print(f"[yellow]miss:[/yellow] {miss}")
    if not result.enriched and not result.skipped and not result.missed:
        _fail("nothing enriched - is the database empty?")


@app.command()
def expand(
    min_ovr: int = typer.Option(..., "--min-ovr", help="Ingest all cards at or above this rating"),
    max_pages: int | None = typer.Option(None, "--max-pages", help="Cap list pages (testing/partial)"),
    db: Path = DB_OPTION,
) -> None:
    """Bulk-ingest the live FUT card pool (base + specials, with prices) from futbin."""
    repo = CardRepository(db)
    try:
        result = expand_cards(
            repo,
            min_ovr=min_ovr,
            fetch_html=fetch_html,
            sleep=time.sleep,
            on_progress=console.print,
            max_pages=max_pages,
        )
    except FC26Error as exc:
        _fail(str(exc))
    console.print(
        f"seen {result.seen}, new {result.new}, merged {result.merged}, "
        f"failed pages {len(result.failed_pages)}"
    )
    for failure in result.failed_pages:
        console.print(f"[yellow]failed:[/yellow] {failure}")
    if result.seen == 0:
        _fail("nothing ingested")
