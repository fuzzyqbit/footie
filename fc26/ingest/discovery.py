"""Discover fcratings player-page URLs via the all-clubs list and club squad pages."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import slugify

ALL_CLUBS_URL = "https://www.fcratings.com/lists/all-clubs"

_PLAYER_LINK_RE = re.compile(
    r'href="https://www\.fcratings\.com/([a-z0-9-]+)-(\d{4,})"'
)


def parse_all_clubs(html: str) -> dict[str, str]:
    """Return {display_name: url, slug: url} for every men's club on the all-clubs page.

    Only anchors inside a ``data-gender="0"`` container are considered; women's
    clubs (``data-gender="1"``) are silently skipped.  This resolves the 11
    display-name collisions between the men's and women's catalogues (e.g.
    "Athletic club" maps to the men's id ``-448`` rather than the women's
    ``-116328``).

    A display name seen with two DIFFERENT urls — even after the gender filter —
    is ambiguous and dropped entirely; the orchestrator records those players as
    misses rather than fetching a guessed squad page.
    """
    tree = HTMLParser(html)
    clubs: dict[str, str] = {}
    ambiguous: set[str] = set()
    for container in tree.css("div[data-gender='0']"):
        for anchor in container.css("a"):
            href = anchor.attributes.get("href") or ""
            if "/clubs/" not in href:
                continue
            display = anchor.text(strip=True)
            if not display:
                continue
            if display in ambiguous:
                continue
            existing = clubs.get(display)
            if existing is not None and existing != href:
                ambiguous.add(display)
                clubs.pop(display, None)
                clubs.pop(slugify(display), None)
                continue
            clubs[display] = href
            clubs[slugify(display)] = href
    return clubs


def find_player_link(club_html: str, player_name: str) -> str | None:
    """Exact slug match for the player on a club squad page; None if absent or ambiguous."""
    target = slugify(player_name)
    urls = {
        f"https://www.fcratings.com/{slug}-{page_id}"
        for slug, page_id in _PLAYER_LINK_RE.findall(club_html)
        if slug == target
    }
    if len(urls) == 1:
        return urls.pop()
    return None
