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
    """Club display name AND its slug alias -> club page URL."""
    tree = HTMLParser(html)
    clubs: dict[str, str] = {}
    for anchor in tree.css("a"):
        href = anchor.attributes.get("href") or ""
        if "/clubs/" not in href:
            continue
        display = anchor.text(strip=True)
        if not display:
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
