"""Parse an fcratings.com player page into a base Card."""

from __future__ import annotations

import datetime
import re
from typing import Optional

from selectolax.parser import HTMLParser

from ..errors import ParseError
from ..models import Card, FaceStats, make_card_id

# Label-to-field mappings for outfield players and GKs.
# Outfield pages have exactly 6 .attr-groups labelled Pace … Physicality.
# GK pages have 7 .attr-groups: the first is "Goalkeeping" (a GK composite)
# followed by the same 6 outfield labels — we skip Goalkeeping and map by label.
_OUTFIELD_LABELS: dict[str, str] = {
    "Pace": "pac",
    "Shooting": "sho",
    "Passing": "pas",
    "Dribbling": "dri",
    "Defending": "def_",
    "Physicality": "phy",
}
_GK_LABELS: dict[str, str] = {
    "Diving": "pac",
    "Handling": "sho",
    "Kicking": "pas",
    "Reflexes": "dri",
    "Speed": "def_",
    "Positioning": "phy",
}

# Regex to extract N-Star values from the meta description or prose paragraph.
_SM_RE = re.compile(r"(\d)-Star Skill Moves")
_WF_RE = re.compile(r"(\d)-Star Weak Foot")


def _require(value: Optional[object], field_name: str, url: str) -> object:
    if value in (None, ""):
        raise ParseError(
            f"missing {field_name} on fcratings page {url} - layout changed?"
        )
    return value


def _text(tree: HTMLParser, selector: str) -> Optional[str]:
    node = tree.css_first(selector)
    return node.text(strip=True) if node else None


def parse_player_page(html: str, source_url: str) -> Card:
    """Parse an fcratings.com player page into a base Card.

    Raises:
        ParseError: if required fields are missing or the page is unrecognised.
    """
    tree = HTMLParser(html)

    # ---- Sentinel check: must look like a player page -----------------------
    if tree.css_first("span.featured-ovr-corner-value") is None:
        raise ParseError(
            f"fcratings page {source_url} is not a player page - "
            "expected featured-ovr-corner-value element"
        )

    # ---- Player name --------------------------------------------------------
    # The h2 in the featured hero area: <h2 ...><span>Kylian</span> <span>Mbappé</span></h2>
    # strip=True on the parent concatenates inner texts without whitespace, so
    # we join the child spans explicitly to preserve the space between given/family name.
    name_node = tree.css_first("h2.h2.text-uppercase.text-white")
    if name_node is not None:
        spans = name_node.css("span")
        if spans:
            name = " ".join(s.text(strip=True) for s in spans if s.text(strip=True))
        else:
            name = name_node.text(strip=False).strip()
    else:
        # Fallback: headshot img title attribute
        img = tree.css_first("img.featured-headshot")
        name = img.attributes.get("title", "").strip() if img else ""
    _require(name or None, "player_name", source_url)
    assert name  # narrowing

    # ---- OVR ----------------------------------------------------------------
    ovr_text = _text(tree, "span.featured-ovr-corner-value")
    _require(ovr_text, "ovr", source_url)
    assert ovr_text is not None
    try:
        ovr = int(ovr_text)
    except ValueError:
        raise ParseError(
            f"non-integer ovr {ovr_text!r} on fcratings page {source_url}"
        )

    # ---- Position -----------------------------------------------------------
    # First custom-pos-badge (no outline modifier) = primary position.
    positions_container = tree.css_first("span.profile-meta-positions")
    if positions_container is None:
        _require(None, "position", source_url)
    assert positions_container is not None

    all_pos_badges = positions_container.css("a.custom-pos-badge")
    if not all_pos_badges:
        _require(None, "position", source_url)

    position = all_pos_badges[0].text(strip=True)
    _require(position or None, "position", source_url)

    # Alt positions: outline-style badges (skip the first primary one)
    alt_positions: tuple[str, ...] = tuple(
        badge.text(strip=True)
        for badge in all_pos_badges[1:]
        if badge.text(strip=True)
    )

    # ---- Club, league, nation -----------------------------------------------
    # first-match on href pattern: breadcrumb/hero/prose all agree today;
    # scope to the hero container if fcratings ever adds cross-club links
    club_link = tree.css_first('a[href*="/clubs/"]')
    club = club_link.text(strip=True) if club_link else None
    _require(club, "club", source_url)

    league_link = tree.css_first('a[href*="/leagues/"]')
    league = league_link.text(strip=True) if league_link else None
    _require(league, "league", source_url)

    nation_link = tree.css_first('a[href*="/nations/"]')
    nation = nation_link.text(strip=True) if nation_link else None
    _require(nation, "nation", source_url)

    # ---- Face stats ---------------------------------------------------------
    # Each .attr-group contains an <h5> label and a span.attr-rating value.
    # Outfield pages have 6 groups labelled Pace/Shooting/Passing/Dribbling/
    # Defending/Physicality. GK pages prepend a "Goalkeeping" group (7 total),
    # which we skip; the remaining 6 still use the same outfield label names.
    # _GK_LABELS is kept for sites that use Diving/Handling/… labels; we probe
    # which map matches the first group label found, defaulting to outfield.
    all_groups = tree.css(".attr-group")
    first_labels = {
        g.css_first("h5").text(strip=True)
        for g in all_groups
        if g.css_first("h5") is not None
    }
    label_map = (
        _GK_LABELS
        if position == "GK" and any(lbl in _GK_LABELS for lbl in first_labels)
        else _OUTFIELD_LABELS
    )
    label_to_value: dict[str, int] = {}
    for group in tree.css(".attr-group"):
        h5 = group.css_first("h5")
        rating = group.css_first("span.attr-rating")
        if h5 is None or rating is None:
            continue
        label = h5.text(strip=True)
        if label not in label_map:
            # Skip unrecognised groups (e.g. "Goalkeeping" composite on GK pages)
            continue
        raw = rating.text(strip=True)
        try:
            label_to_value[label] = int(raw)
        except ValueError:
            raise ParseError(
                f"non-integer face stat {label!r}={raw!r} on fcratings page {source_url}"
            )

    # Verify every expected label was found
    for label in label_map:
        if label not in label_to_value:
            raise ParseError(
                f"missing face-stat label {label!r} on fcratings page {source_url} "
                "- layout changed?"
            )

    # Build field→value using the label map (label→field) as a bridge
    field_to_value = {field: label_to_value[label] for label, field in label_map.items()}

    face = FaceStats(
        pac=field_to_value["pac"],
        sho=field_to_value["sho"],
        pas=field_to_value["pas"],
        dri=field_to_value["dri"],
        def_=field_to_value["def_"],
        phy=field_to_value["phy"],
    )

    # ---- Skill moves and weak foot ------------------------------------------
    # These are only present as text in the meta description and the prose paragraph.
    # Parse from meta[name="description"] content, then fallback to the prose para.
    skill_moves: Optional[int] = None
    weak_foot: Optional[int] = None

    meta_desc_node = tree.css_first('meta[name="description"]')
    desc_text: str = ""
    if meta_desc_node is not None:
        desc_text = meta_desc_node.attributes.get("content", "")

    if not desc_text:
        # Fallback: scan entire text for the pattern
        desc_text = html

    sm_match = _SM_RE.search(desc_text)
    if sm_match:
        skill_moves = int(sm_match.group(1))

    wf_match = _WF_RE.search(desc_text)
    if wf_match:
        weak_foot = int(wf_match.group(1))

    # ---- Assemble and return ------------------------------------------------
    return Card(
        id=make_card_id(name, "base"),
        player_name=name,
        version="base",
        ovr=ovr,
        position=position,
        alt_positions=alt_positions,
        face=face,
        skill_moves=skill_moves,
        weak_foot=weak_foot,
        club=club,
        league=league,
        nation=nation,
        source_url=source_url,
        crawled_at=datetime.date.today().isoformat(),
    )
