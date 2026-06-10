"""fut.gg per-card page parser and fetcher."""

from __future__ import annotations

import datetime
import re
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

from fc26.errors import FetchError, ParseError
from fc26.models import Card, FaceStats, SubStats, make_card_id

USER_AGENT = "footie-playbook/0.1 (personal squad tool)"
TIMEOUT_SECONDS = 15

# ---------------------------------------------------------------------------
# DOM icon paths used to distinguish PlayStyles+ (pentagon) from PlayStyles (diamond)
# ---------------------------------------------------------------------------

_PENTAGON_PATH = "M12.813,104.953L68.157,21.862H188.143l55.045,83.091L128,235.138Z"
_DIAMOND_PATH = "M128,12.808L243.192,128,128,243.192,12.808,128Z"

# ---------------------------------------------------------------------------
# DOM label -> SubStats field name mapping (all 29 sub-stats)
# ---------------------------------------------------------------------------

_DOM_LABEL_TO_FIELD: dict[str, str] = {
    "Acceleration": "acceleration",
    "Sprint Speed": "sprint_speed",
    "Att. Pos.": "positioning",
    "Finishing": "finishing",
    "Shot Power": "shot_power",
    "Long Shots": "long_shots",
    "Volleys": "volleys",
    "Penalties": "penalties",
    "Vision": "vision",
    "Crossing": "crossing",
    "Fk Acc.": "fk_accuracy",
    "Short Pass": "short_passing",
    "Long Pass": "long_passing",
    "Curve": "curve",
    "Agility": "agility",
    "Balance": "balance",
    "Reactions": "reactions",
    "Ball Control": "ball_control",
    "Dribbling": "dribbling",
    "Composure": "composure",
    "Interceptions": "interceptions",
    "Heading Acc.": "heading_accuracy",
    "Def. Aware.": "def_awareness",
    "Stand Tackle": "standing_tackle",
    "Slide Tackle": "sliding_tackle",
    "Jumping": "jumping",
    "Stamina": "stamina",
    "Strength": "strength",
    "Aggression": "aggression",
}

# ---------------------------------------------------------------------------
# JS blob extraction helpers
# ---------------------------------------------------------------------------

_JS_BLOB_RE = re.compile(
    r"<script[^>]*>(.*?facePace.*?)</script>", re.DOTALL
)


def _extract_js_blob(html: str) -> Optional[str]:
    """Return the first <script> text that contains the facePace field, or None."""
    m = _JS_BLOB_RE.search(html)
    return m.group(1) if m else None


def _js_str(blob: str, key: str) -> Optional[str]:
    """Extract a string value: key:"value" from JS blob."""
    m = re.search(rf'{re.escape(key)}:"([^"]*)"', blob)
    return m.group(1) if m else None


def _js_int(blob: str, key: str) -> Optional[int]:
    """Extract an integer value: key:digits from JS blob."""
    m = re.search(rf'{re.escape(key)}:(\d+)', blob)
    return int(m.group(1)) if m else None


def _js_int_in_section(blob: str, anchor: str, key: str) -> Optional[int]:
    """Extract an integer value from a section starting at anchor."""
    idx = blob.find(anchor)
    if idx < 0:
        return None
    section = blob[idx:idx + 2000]
    return _js_int(section, key)


def _js_str_in_section(blob: str, anchor: str, key: str) -> Optional[str]:
    """Extract a string value from a section starting at anchor."""
    idx = blob.find(anchor)
    if idx < 0:
        return None
    section = blob[idx:idx + 2000]
    return _js_str(section, key)


def _require(value: Optional[object], field: str, source_url: str) -> object:
    """Raise ParseError if value is None."""
    if value is None:
        raise ParseError(
            f"missing {field} on fut.gg page {source_url} - layout changed?"
        )
    return value


# ---------------------------------------------------------------------------
# Sub-stat extraction from DOM
# ---------------------------------------------------------------------------

_STAT_LABEL_RE = re.compile(
    r'<div class="overflow-hidden text-ellipsis whitespace-nowrap text-xs md:text-sm">'
    r"([^<]+)</div>"
    r".*?"
    r'<span class="text-sm font-bold text-white"[^>]*>(\d+)</span>',
    re.DOTALL,
)


def _extract_subs(html: str) -> Optional[SubStats]:
    """Extract all 29 sub-stats from the DOM stat table."""
    # The DOM stats section starts after the large JS blob; search from position 200000
    # to avoid false matches in the JS data.
    search_start = html.find("Acceleration", 200_000)
    if search_start < 0:
        # Fallback: try from beginning
        search_start = 0

    section = html[max(0, search_start - 500) : search_start + 30_000]
    pairs = _STAT_LABEL_RE.findall(section)

    field_values: dict[str, int] = {}
    for label, val in pairs:
        field = _DOM_LABEL_TO_FIELD.get(label.strip())
        if field:
            field_values[field] = int(val)

    if not field_values:
        return None

    return SubStats(**field_values)


# ---------------------------------------------------------------------------
# Playstyle extraction from DOM
# ---------------------------------------------------------------------------

def _extract_playstyles(
    html: str, blob: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (playstyles, playstyles_plus) as tuples of names.

    Pentagon icon (PS+) vs diamond icon (regular PS) distinguishes the groups.
    The DOM renders PS+ first (pentagon), then regular PS (diamond).
    """
    span_re = re.compile(
        r'<span class="overflow-hidden">([^<]+)</span>'
    )
    svg_42_re = re.compile(
        r'<svg[^>]+height="42"[^>]*>(.*?)</svg>', re.DOTALL
    )

    # Determine the expected counts from the JS blob for validation
    ps_count_match = re.search(
        r"playstyles:\$R\[\d+\]=\[([\d,]+)\]", blob
    )
    psplus_count_match = re.search(
        r"playstylesPlus:\$R\[\d+\]=\[([\d,]+)\]", blob
    )

    ps_plus: list[str] = []
    ps_regular: list[str] = []

    for m in span_re.finditer(html):
        label = m.group(1)
        pos = m.start()
        # Look back up to 5000 chars for the containing 42x42 SVG
        pre = html[max(0, pos - 5000) : pos]
        # Find the last height="42" SVG in pre-context
        last_svg_match = None
        for svg_m in svg_42_re.finditer(pre):
            last_svg_match = svg_m

        if last_svg_match is None:
            continue

        svg_content = last_svg_match.group(1)
        if _PENTAGON_PATH in svg_content:
            ps_plus.append(label)
        elif _DIAMOND_PATH in svg_content:
            ps_regular.append(label)

    return tuple(ps_regular), tuple(ps_plus)


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_futgg_card(html: str, source_url: str) -> Card:
    """Parse a fut.gg per-card HTML page into a Card.

    Raises:
        ParseError: if required fields are missing or the page is unrecognised.
    """
    blob = _extract_js_blob(html)
    if blob is None:
        raise ParseError(
            f"fut.gg page did not contain expected data blob — "
            f"layout changed? ({source_url})"
        )

    # ---- Required fields --------------------------------------------------

    # Player name: commonName or cardName in JS blob
    player_name = _js_str(blob, "commonName") or _js_str(blob, "cardName")
    _require(player_name, "player_name", source_url)
    assert player_name is not None  # narrowing for type checker

    # Card version: rarityName
    version = _js_str(blob, "rarityName")
    _require(version, "version", source_url)
    assert version is not None

    # OVR + position: co-located in the card presentation object as
    # overall:96,position:"CDM"
    ovr_pos_match = re.search(r'overall:(\d+),position:"([^"]+)"', blob)
    if ovr_pos_match is None:
        _require(None, "ovr/position", source_url)
    assert ovr_pos_match is not None

    overall = int(ovr_pos_match.group(1))
    position = ovr_pos_match.group(2)
    _require(overall, "ovr", source_url)
    _require(position, "position", source_url)

    # Alt positions: from alternativePositions:$R[N]=["CM"] pattern
    alt_pos_match = re.search(
        r'alternativePositions:\$R\[\d+\]=\[([^\]]*)\]', blob
    )
    alt_positions: tuple[str, ...] = ()
    if alt_pos_match and alt_pos_match.group(1).strip():
        raw = alt_pos_match.group(1)
        alt_positions = tuple(
            s.strip().strip('"') for s in raw.split(",") if s.strip().strip('"')
        )

    # Face stats
    face_pac = _js_int(blob, "facePace")
    face_sho = _js_int(blob, "faceShooting")
    face_pas = _js_int(blob, "facePassing")
    face_dri = _js_int(blob, "faceDribbling")
    face_def = _js_int(blob, "faceDefending")
    face_phy = _js_int(blob, "facePhysicality")

    _require(face_pac, "face.pac", source_url)
    _require(face_sho, "face.sho", source_url)
    _require(face_pas, "face.pas", source_url)
    _require(face_dri, "face.dri", source_url)
    _require(face_def, "face.def_", source_url)
    _require(face_phy, "face.phy", source_url)

    face = FaceStats(
        pac=face_pac,
        sho=face_sho,
        pas=face_pas,
        dri=face_dri,
        def_=face_def,
        phy=face_phy,
    )

    # ---- Optional fields --------------------------------------------------

    # AcceleRATE: from DOM li with AcceleRATE label
    accelerate: Optional[str] = None
    tree = HTMLParser(html)
    for li in tree.css("li"):
        spans = li.css("span")
        if len(spans) >= 2 and "AcceleRATE" in spans[0].text():
            raw_acc = spans[1].text().strip()
            if raw_acc:
                accelerate = raw_acc
            break

    # Skill moves and weak foot from JS blob
    skill_moves = _js_int_in_section(blob, "playerDef:", "skillMoves")
    weak_foot = _js_int_in_section(blob, "playerDef:", "weakFoot")

    # Height from JS blob (in the playerDef section)
    height_cm = _js_int_in_section(blob, "playerDef:", "height")

    # Age: calculate from dateOfBirth
    age: Optional[int] = None
    dob_match = re.search(r'dateOfBirth:"(\d{4}-\d{2}-\d{2})"', blob)
    if dob_match:
        try:
            dob = datetime.date.fromisoformat(dob_match.group(1))
            today = datetime.date.today()
            age = (
                today.year
                - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )
        except ValueError:
            pass

    # Club, league, nation from DOM links
    club: Optional[str] = None
    league: Optional[str] = None
    nation: Optional[str] = None

    club_link = tree.css_first('a[href^="/clubs/"]')
    if club_link:
        span = club_link.css_first("span.truncate")
        if span:
            club = span.text().strip() or None

    league_link = tree.css_first('a[href^="/leagues/"]')
    if league_link:
        span = league_link.css_first("span.truncate")
        if span:
            league = span.text().strip() or None

    nation_link = tree.css_first('a[href^="/nations/"]')
    if nation_link:
        span = nation_link.css_first("span.truncate")
        if span:
            nation = span.text().strip() or None

    # Sub-stats from DOM
    subs = _extract_subs(html)

    # Playstyles from DOM
    playstyles, playstyles_plus = _extract_playstyles(html, blob)

    # Card id
    card_id = make_card_id(player_name, version)

    return Card(
        id=card_id,
        player_name=player_name,
        version=version,
        ovr=overall,
        position=position,
        alt_positions=alt_positions,
        face=face,
        subs=subs,
        playstyles=playstyles,
        playstyles_plus=playstyles_plus,
        accelerate=accelerate,
        skill_moves=skill_moves,
        weak_foot=weak_foot,
        club=club,
        league=league,
        nation=nation,
        height_cm=height_cm,
        age=age,
        source_url=source_url,
        crawled_at=datetime.date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

def fetch_futgg_card(url: str) -> Card:
    """Fetch and parse a fut.gg per-card page.

    Performs one retry on httpx.HTTPError before raising FetchError.

    Raises:
        FetchError: after retry exhaustion.
        ParseError: if the page cannot be parsed.
    """
    last_error: Optional[Exception] = None
    for _attempt in range(2):
        try:
            response = httpx.get(
                url,
                timeout=TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            return parse_futgg_card(response.text, source_url=url)
        except httpx.HTTPError as exc:
            last_error = exc

    raise FetchError(f"could not fetch {url}: {last_error}")
