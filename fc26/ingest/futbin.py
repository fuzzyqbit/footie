"""Parse futbin player-list pages into Cards (bulk expansion source)."""

from __future__ import annotations

import datetime
import re

from selectolax.parser import HTMLParser

from ..errors import ParseError
from ..models import Card, FaceStats, VALID_POSITIONS, make_card_id

LIST_URL_TEMPLATE = "https://www.futbin.com/players?player_rating={min_ovr}-99&page={page}"  # consumed by the expand orchestrator
ROWS_PER_FULL_PAGE = 30  # consumed by the expand orchestrator

# futbin badge texts that mean "this is the plain base card".
# Live site uses "Normal" (verified 2026-06-10); gold/silver entries kept
# as defensive aliases in case futbin renames tiers.
# Stored lowercase so that _normalize_version can do a case-insensitive
# exact-match without substring ambiguity (e.g. "Base Heroes" must NOT match).
_BASE_VERSIONS_LOWER = {
    "normal",
    "gold rare",
    "gold common",
    "gold nr",
    "gold",
    "silver rare",
    "silver common",
    "silver nr",
    "silver",
    "bronze rare",
    "bronze common",
    "bronze nr",
    "bronze",
}


def _normalize_version(badge_text: str) -> str:
    """Map base-card badges to 'base' (case-insensitive); specials stay verbatim."""
    text = (badge_text or "").strip()
    if text.lower() in _BASE_VERSIONS_LOWER:
        return "base"
    return text or "base"

# Regex to extract the leading cm value from height cells like "178cm | 5'10""
_HEIGHT_RE = re.compile(r"(\d{2,3})cm")


def _clean_alt_positions(raw_tokens: list[str]) -> tuple[str, ...]:
    """Filter alt-position tokens to only those in VALID_POSITIONS.

    futbin sometimes appends "+N" tokens (e.g. "+1") when a card has more
    alt positions than the UI can display. Strip these and any other invalid tokens.
    """
    return tuple(
        p.strip() for p in raw_tokens
        if p.strip() in VALID_POSITIONS
    )


def parse_price(raw: str) -> int | None:
    """'3.02M' -> 3_020_000, '750K' -> 750_000, '12,500' -> 12_500; junk/zero -> None."""
    text = (raw or "").strip().replace(",", "")
    if not text:
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([MK]?)", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "M":
        value *= 1_000_000
    elif unit == "K":
        value *= 1_000
    price = int(value)
    return price if price > 0 else None


def _parse_row(row_html: str, source_url: str) -> Card | None:
    """Parse a single player-row TR into a Card; return None if required fields are missing."""
    tree = HTMLParser("<table><tbody>" + row_html + "</tbody></table>")

    # --- Player name ---
    name_link = tree.css_first(".table-player-name")
    if name_link is None:
        return None
    player_name = name_link.text(strip=True)
    if not player_name:
        return None

    # --- OVR ---
    rating_td = tree.css_first("td.table-rating")
    if rating_td is None:
        return None
    ovr_text = rating_td.text(strip=True)
    try:
        ovr = int(ovr_text)
    except (ValueError, TypeError):
        return None

    # --- Version badge ---
    version_div = tree.css_first(".table-player-revision")
    badge_text = version_div.text(strip=True) if version_div else ""
    version = _normalize_version(badge_text)

    # --- Position ---
    pos_td = tree.css_first("td.table-pos")
    if pos_td is None:
        return None
    pos_main = pos_td.css_first(".table-pos-main span")
    if pos_main is None:
        return None
    position = pos_main.text(strip=True)
    if not position:
        return None

    # --- Alt positions ---
    alt_div = pos_td.css_first("div.xs-font")
    if alt_div:
        alt_text = alt_div.text(strip=True)
        alt_positions = _clean_alt_positions(alt_text.split(","))
    else:
        alt_positions = ()

    # --- Face stats (required) ---
    pac_td = tree.css_first("td.table-pace")
    sho_td = tree.css_first("td.table-shooting")
    pas_td = tree.css_first("td.table-passing")
    dri_td = tree.css_first("td.table-dribbling")
    def_td = tree.css_first("td.table-defending")
    phy_td = tree.css_first("td.table-physicality")

    face_cells = (pac_td, sho_td, pas_td, dri_td, def_td, phy_td)
    if any(td is None for td in face_cells):
        return None

    try:
        face = FaceStats(
            pac=int(pac_td.text(strip=True)),
            sho=int(sho_td.text(strip=True)),
            pas=int(pas_td.text(strip=True)),
            dri=int(dri_td.text(strip=True)),
            def_=int(def_td.text(strip=True)),
            phy=int(phy_td.text(strip=True)),
        )
    except (ValueError, TypeError):
        return None

    # --- Skill moves ---
    sm_td = tree.css_first("td.table-skills")
    skill_moves: int | None = None
    if sm_td:
        m = re.search(r"(\d)", sm_td.text(strip=True))
        if m:
            skill_moves = int(m.group(1))

    # --- Weak foot ---
    wf_td = tree.css_first("td.table-weak-foot")
    weak_foot: int | None = None
    if wf_td:
        m = re.search(r"(\d)", wf_td.text(strip=True))
        if m:
            weak_foot = int(m.group(1))

    # --- Height & AcceleRATE ---
    height_cm: int | None = None
    accelerate: str | None = None
    height_td = tree.css_first("td.table-height")
    if height_td:
        height_text = height_td.text(strip=True)
        h_match = _HEIGHT_RE.search(height_text)
        if h_match:
            height_cm = int(h_match.group(1))
        accel_link = height_td.css_first("a")
        if accel_link:
            accelerate = accel_link.text(strip=True) or None

    # --- Nation / League / Club from sub-info images ---
    nation: str | None = None
    league: str | None = None
    club: str | None = None
    sub_info = tree.css_first(".table-player-sub-info")
    if sub_info:
        for img in sub_info.css("img"):
            alt = img.attributes.get("alt", "")
            title = img.attributes.get("title", "") or None
            if alt == "Nation":
                nation = title
            elif alt == "League":
                league = title
            elif alt == "Club":
                club = title

    # --- Price (PS platform price preferred) ---
    # PS prices preferred: this project targets PS5. futbin exposes per-platform
    # cells (platform-ps-only / platform-xbox-only / platform-pc-only).
    price: int | None = None
    price_td = tree.css_first("td.platform-ps-only")
    if price_td:
        price_div = price_td.css_first("div.price.bold")
        if price_div:
            # The div contains the price text followed by a coin <img>; text() includes
            # alt text from the img ("Coin"), so we strip that.
            raw_price = re.sub(r"coins?", "", price_div.text(strip=True), flags=re.IGNORECASE).strip()
            price = parse_price(raw_price)

    # --- Build card ---
    card_id = make_card_id(player_name, version)
    today = datetime.date.today().isoformat()

    return Card(
        id=card_id,
        player_name=player_name,
        version=version,
        ovr=ovr,
        position=position,
        alt_positions=alt_positions,
        face=face,
        skill_moves=skill_moves,
        weak_foot=weak_foot,
        height_cm=height_cm,
        accelerate=accelerate,
        nation=nation,
        league=league,
        club=club,
        price=price,
        source_url=source_url,
        crawled_at=today,
    )


def parse_futbin_page(html: str, source_url: str) -> list[Card]:
    """Parse a futbin player-list page into a list of Cards.

    Raises:
        ParseError: if no player rows are found, or more than half the rows
                    cannot be parsed (indicating a layout change).
    """
    tree = HTMLParser(html)
    # Player rows are <tr> elements that *contain* an <a class="player-row-playercard">
    # The anchor is inside a <td class="table-name"> inside the TR.
    rows = tree.css('tr.player-row')
    if not rows:
        raise ParseError(
            f"no player rows on futbin page {source_url} - layout changed?"
        )

    cards: list[Card] = []
    skipped = 0

    for row in rows:
        row_html = row.html or ""
        if not row_html:
            skipped += 1
            continue
        card = _parse_row(row_html, source_url)
        if card is None:
            skipped += 1
        else:
            cards.append(card)

    if skipped > len(rows) // 2:
        raise ParseError(
            f"{skipped}/{len(rows)} rows unparseable on futbin page {source_url} - layout changed?"
        )

    return cards
