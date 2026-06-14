"""fc26 command-line interface."""

from __future__ import annotations

import json as json_lib
import time
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

from .builder.advise import advise_squad
from .builder.boost import boosted_stats
from .builder.build import build_squad
from .builder.market import parse_budget
from .builder.plan import plan_for_squad, plan_from_scratch
from .builder.upgrade import find_upgrades
from .chem.engine import compute_chemistry
from .chem.lineup import load_lineup, resolve_cards
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


@app.command()
def upgrade(
    squad_file: Path = typer.Argument(..., help="Path to a squad JSON file"),
    budget: str = typer.Option(..., "--budget", help="Net spend cap, e.g. 100K, 1.2M"),
    swaps: int = typer.Option(3, "--swaps", help="Max swaps to suggest"),
    write: Path | None = typer.Option(None, "--write", help="Save upgraded squad to a NEW file"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """Suggest budgeted squad upgrades (pace-meta + chemistry aware)."""
    try:
        coins = parse_budget(budget)
        lineup = load_lineup(squad_file)
        repo = CardRepository(db)
        slot_cards = resolve_cards(lineup, repo)
        plan = find_upgrades(lineup, slot_cards, repo.find_all(),
                             budget=coins, max_swaps=swaps)
    except FC26Error as exc:
        _fail(str(exc))
    if write is not None and write.resolve() == squad_file.resolve():
        _fail("--write must target a NEW file, not the input")
    if json:
        typer.echo(json_lib.dumps(asdict(plan), ensure_ascii=False, indent=2))
    elif not plan.swaps:
        console.print("no upgrades found within budget")
    else:
        table = Table("Slot", "Out", "Resale", "In", "Price", "Net", "Δmeta", "Δchem")
        for s in plan.swaps:
            table.add_row(
                s.slot, f"{s.out_name} ({s.out_version})", str(s.out_resale),
                f"{s.in_name} ({s.in_version})", str(s.in_price), str(s.net_cost),
                f"{s.meta_delta:+.1f}", f"{s.chem_delta:+d}",
            )
        console.print(table)
        console.print(
            f"spent {plan.spent} of {plan.budget} | squad score "
            f"{plan.score_before:.1f} → {plan.score_after:.1f} | "
            f"chem {plan.chem_before} → {plan.chem_after}"
        )
    if not json:
        for warning in plan.warnings:
            console.print(f"[yellow]warn:[/yellow] {warning}")
    if write is not None:
        swapped = dict(lineup.slots)
        for s in plan.swaps:
            swapped[s.slot] = s.in_id
        payload: dict = {
            "name": f"{lineup.name} (upgraded)",
            "formation": lineup.formation,
            "starting_xi": {slot: swapped[slot] for slot, _ in lineup.slots},
        }
        if lineup.manager is not None:
            manager: dict = {}
            if lineup.manager.league:
                manager["league"] = lineup.manager.league
            if lineup.manager.nation:
                manager["nation"] = lineup.manager.nation
            payload["manager"] = manager
        write.write_text(json_lib.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        console.print(f"upgraded squad written to {write}")


@app.command()
def build(
    formation: str = typer.Option(..., "--formation", help="e.g. 4-2-3-1"),
    budget: str = typer.Option(..., "--budget", help="Total budget, e.g. 500K"),
    league: str | None = typer.Option(None, "--league", help="Restrict pool to one league"),
    write: Path | None = typer.Option(None, "--write", help="Save built squad to a file"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """Build a fresh XI from scratch: cheapest legal seed, then budgeted upgrades."""
    try:
        coins = parse_budget(budget)
        repo = CardRepository(db)
        result = build_squad(formation, repo.find_all(), budget=coins, league=league)
    except FC26Error as exc:
        _fail(str(exc))
    report = compute_chemistry(result.lineup, result.slot_cards)
    xi_payload = [
        {"slot": slot, "card_id": card.id, "player_name": card.player_name,
         "version": card.version, "price": card.price}
        for slot, card in ((s, result.slot_cards[s]) for s, _ in result.lineup.slots)
    ]
    if json:
        typer.echo(json_lib.dumps({
            "formation": formation, "budget": coins,
            "seed_cost": result.seed_cost, "total_cost": result.total_cost,
            "team_chem": report.team_total, "xi": xi_payload,
        }, ensure_ascii=False, indent=2))
    else:
        table = Table("Slot", "Player", "Version", "Price")
        for entry in xi_payload:
            table.add_row(entry["slot"], entry["player_name"], entry["version"],
                          str(entry["price"]))
        console.print(table)
        console.print(
            f"total cost {result.total_cost} of {coins} | "
            f"team chemistry {report.team_total}/33"
        )
    if write is not None:
        payload = {
            "name": result.lineup.name,
            "formation": formation,
            "starting_xi": {slot: result.slot_cards[slot].id
                            for slot, _ in result.lineup.slots},
        }
        write.write_text(json_lib.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        console.print(f"built squad written to {write}")


@app.command()
def plan(
    squad_file: Path | None = typer.Argument(None, help="Squad JSON for upgrade-mode planning"),
    formation: str | None = typer.Option(None, "--formation", help="Build-mode formation, e.g. 4-2-3-1"),
    budget: str = typer.Option(..., "--budget", help="Total budget cap, e.g. 500K"),
    league: str | None = typer.Option(None, "--league", help="Build-mode: restrict pool to one league"),
    swaps: int = typer.Option(3, "--swaps", help="Upgrade-mode: max swaps to suggest"),
    write: Path | None = typer.Option(None, "--write", help="Save the final squad to a NEW file"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """Ordered acquisition plan: what to buy now, then the budgeted upgrade path with ROI."""
    if squad_file is not None and formation is not None:
        _fail("pass either a squad file (upgrade mode) or --formation (build mode), not both")
    if squad_file is None and formation is None:
        _fail("give a squad file (upgrade mode) or --formation (build mode)")
    if write is not None and squad_file is not None and write.resolve() == squad_file.resolve():
        _fail("--write must target a NEW file, not the input")
    lineup = None
    try:
        coins = parse_budget(budget)
        repo = CardRepository(db)
        pool = repo.find_all()
        if squad_file is not None:
            lineup = load_lineup(squad_file)
            slot_cards = resolve_cards(lineup, repo)
            acq = plan_for_squad(lineup, slot_cards, pool, budget=coins, max_swaps=swaps)
        else:
            acq = plan_from_scratch(formation, pool, budget=coins, league=league)
    except FC26Error as exc:
        _fail(str(exc))

    if json:
        typer.echo(json_lib.dumps(asdict(acq), ensure_ascii=False, indent=2))
    else:
        if acq.seed:
            seed_table = Table("Slot", "Player", "Version", "Price")
            for sb in acq.seed:
                seed_table.add_row(sb.slot, sb.player_name, sb.version, str(sb.price))
            console.print("[bold]Buy now — starting XI[/bold]")
            console.print(seed_table)
            console.print(f"seed cost {acq.seed_cost}")
        if acq.steps:
            path = Table("#", "Slot", "Out", "In", "Net", "Spent", "Left",
                         "Score", "Chem", "ROI/1k")
            for st in acq.steps:
                roi = "free" if st.roi is None else f"{st.roi * 1000:.1f}"
                path.add_row(
                    str(st.index), st.slot,
                    f"{st.out_name} ({st.out_version})",
                    f"{st.in_name} ({st.in_version})",
                    str(st.net_cost), str(st.cumulative_spent), str(st.remaining),
                    f"{st.score_after:.1f}", str(st.chem_after), roi,
                )
            console.print("[bold]Upgrade path[/bold]")
            console.print(path)
        else:
            console.print("no upgrades found within budget")
        console.print(
            f"total cost {acq.total_spent} of {acq.budget} | squad score "
            f"{acq.base_score:.1f} → {acq.final_score:.1f} | "
            f"chem {acq.base_chem} → {acq.final_chem}"
        )
        for warning in acq.warnings:
            console.print(f"[yellow]warn:[/yellow] {warning}")

    if write is not None:
        if lineup is not None:
            final_ids = {slot: card_id for slot, card_id in lineup.slots}
            name = f"{lineup.name} (planned)"
            order = [slot for slot, _ in lineup.slots]
        else:
            final_ids = {sb.slot: sb.card_id for sb in acq.seed}
            name = f"Planned {acq.formation}"
            order = [sb.slot for sb in acq.seed]
        for st in acq.steps:
            final_ids[st.slot] = st.in_id
        payload: dict = {
            "name": name,
            "formation": acq.formation,
            "starting_xi": {slot: final_ids[slot] for slot in order},
        }
        if lineup is not None and lineup.manager is not None:
            manager: dict = {}
            if lineup.manager.league:
                manager["league"] = lineup.manager.league
            if lineup.manager.nation:
                manager["nation"] = lineup.manager.nation
            payload["manager"] = manager
        write.write_text(json_lib.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        console.print(f"plan squad written to {write}")


@app.command()
def chem(
    squad_file: Path = typer.Argument(..., help="Path to a squad JSON file (see squads/)"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """Compute FC26 chemistry for a lineup file."""
    try:
        lineup = load_lineup(squad_file)
        slot_cards = resolve_cards(lineup, CardRepository(db))
    except FC26Error as exc:
        _fail(str(exc))
    report = compute_chemistry(lineup, slot_cards)
    if json:
        typer.echo(json_lib.dumps(asdict(report), ensure_ascii=False, indent=2))
        return
    table = Table("Slot", "Player", "Version", "Pos", "In pos", "Chem")
    for p in report.players:
        table.add_row(p.slot, p.player_name, p.version, p.position,
                      "✓" if p.in_position else "✗", str(p.chem))
    console.print(table)
    console.print(f"[bold]team chemistry: {report.team_total}/33[/bold]")
    # "Strength" is the weighted chemistry count (icons 2x nation, heroes 2x league),
    # NOT a human headcount - do not relabel as "players"
    breakdown = Table("Type", "Group", "Strength", "Points", "Next tier")
    for t in report.tiers:
        hint = f"+{t.next_tier_at - t.count} more" if t.next_tier_at else "max"
        breakdown.add_row(t.kind, t.name, str(t.count), str(t.points), hint)
    console.print(breakdown)
    for warning in report.warnings:
        console.print(f"[yellow]warn:[/yellow] {warning}")


@app.command()
def advise(
    squad_file: Path = typer.Argument(..., help="Path to a squad JSON file"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """Strategy tips: chem leverage, out-of-position, weak slots, best chem styles."""
    try:
        lineup = load_lineup(squad_file)
        slot_cards = resolve_cards(lineup, CardRepository(db))
    except FC26Error as exc:
        _fail(str(exc))
    advice = advise_squad(lineup, slot_cards)
    if json:
        typer.echo(json_lib.dumps(asdict(advice), ensure_ascii=False, indent=2))
        return
    console.print(f"[bold]Advice — {advice.formation} · chem {advice.team_chem}/33[/bold]")
    for line in advice.summary:
        console.print(f"• {line}")
    if advice.out_of_position:
        console.print("[bold]Out of position[/bold]")
        for n in advice.out_of_position:
            console.print(f"  {n.slot}: {n.player_name} — {n.reason}")
    if advice.tier_leverage:
        table = Table("Kind", "Group", "Have", "Pts", "To next")
        for lv in advice.tier_leverage[:8]:
            table.add_row(lv.kind, lv.name, str(lv.count), str(lv.points), f"+{lv.needed}")
        console.print("[bold]Chem leverage[/bold]")
        console.print(table)
    if advice.weakest_slots:
        table = Table("Slot", "Player", "Pos", "Meta")
        for n in advice.weakest_slots:
            table.add_row(n.slot, n.player_name, n.position, f"{n.meta:.0f}")
        console.print("[bold]Weakest slots[/bold]")
        console.print(table)
    picks = [s for s in advice.style_advice if s.recommended_style]
    if picks:
        table = Table("Slot", "Player", "Style", "+Meta")
        for s in picks:
            table.add_row(s.slot, s.player_name, s.recommended_style, f"+{s.meta_gain:.1f}")
        console.print("[bold]Best chem styles[/bold]")
        console.print(table)
    for warning in advice.warnings:
        console.print(f"[yellow]warn:[/yellow] {warning}")


@app.command()
def boost(
    squad_file: Path = typer.Argument(..., help="Squad JSON (slots may carry styles)"),
    db: Path = DB_OPTION,
    json: bool = JSON_FLAG,
) -> None:
    """Show chem-gated boosted stats for a styled lineup."""
    try:
        lineup = load_lineup(squad_file)
        slot_cards = resolve_cards(lineup, CardRepository(db))
        report = compute_chemistry(lineup, slot_cards)
        chem_by_slot = {p.slot: p.chem for p in report.players}
        results = []
        for slot, _cid in lineup.slots:
            card = slot_cards[slot]
            style = lineup.styles.get(slot)
            results.append((slot, card, style,
                            boosted_stats(card, style, chem_by_slot[slot])))
    except FC26Error as exc:
        _fail(str(exc))
    if json:
        payload = [{
            "slot": slot, "card_id": card.id, "player_name": card.player_name,
            "style": style, "chem": chem_by_slot[slot], "precision": r.precision,
            "face": asdict(r.face), "subs": asdict(r.subs) if r.subs else None,
        } for slot, card, style, r in results]
        typer.echo(json_lib.dumps({"players": payload, "team_chem": report.team_total},
                                  ensure_ascii=False, indent=2))
        return
    table = Table("Slot", "Player", "Style", "Chem", "PAC", "SHO", "PAS", "DRI", "DEF", "PHY")
    any_approx = False
    for slot, card, style, r in results:
        marker = "≈" if r.precision != "none" else ""
        if r.precision == "approx":
            any_approx = True

        def cell(face_name, _card=card, _r=r, _marker=marker):
            base = getattr(_card.face, face_name)
            boosted_value = getattr(_r.face, face_name)
            if base is None or boosted_value is None:
                return "-"
            if boosted_value != base:
                return f"{boosted_value}{_marker}(+{boosted_value - base})"
            return str(base)

        table.add_row(slot, card.player_name, style or "-", str(chem_by_slot[slot]),
                      cell("pac"), cell("sho"), cell("pas"),
                      cell("dri"), cell("def_"), cell("phy"))
    console.print(table)
    console.print(f"team chemistry: {report.team_total}/33")
    for slot, card, style, r in results:
        if style and chem_by_slot[slot] == 0:
            console.print(f"[yellow]warn:[/yellow] {card.id}: styled but 0 chem - style has no effect")
    if any_approx:
        console.print("[dim]≈ approximate faces - add cards via `fc26 add <fut.gg URL>` for sub-level precision[/dim]")


@app.command()
def serve(
    port: int = typer.Option(8026, "--port", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind (0.0.0.0 = all interfaces)"),
    db: Path = DB_OPTION,
    squads: Path = typer.Option(Path("squads"), "--squads", help="Squad files directory"),
) -> None:
    """Start the FC 26 API server (no auth — local network only)."""
    import uvicorn
    from .api.app import create_app

    api = create_app(db_path=db, squads_dir=squads)
    uvicorn.run(api, host=host, port=port)
