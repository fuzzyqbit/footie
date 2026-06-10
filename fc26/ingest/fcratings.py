"""fcratings.com top-100 list parser and fetcher."""

from __future__ import annotations

import datetime
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

from fc26.errors import FetchError, ParseError
from fc26.models import Card, make_card_id

USER_AGENT = "footie-playbook/0.1 (personal squad tool)"
TIMEOUT_SECONDS = 15

# Minimum number of cards that must be parsed before we consider the result valid.
_MIN_CARDS = 50

# CSS selector for the ratings table.
_TABLE_SELECTOR = "table.custom-table"


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------


def parse_top100_page(html: str, source_url: str) -> list[Card]:
    """Parse an fcratings.com top-100 list page into a list of Cards.

    Raises:
        ParseError: if the page is unrecognised or too few cards are found.
    """
    tree = HTMLParser(html)
    table = tree.css_first(_TABLE_SELECTOR)
    if table is None:
        raise ParseError(
            f"fcratings page {source_url} did not contain expected ratings table "
            f"- layout changed?"
        )

    rows = table.css("tr")
    today = datetime.date.today().isoformat()
    cards: list[Card] = []

    for row in rows:
        tds = row.css("td")
        # Data rows have at least 3 columns; header rows use <th>, not <td>.
        if len(tds) < 3:
            continue

        name_div = row.css_first("div.custom-name")
        ovr_td = tds[2]
        pos_badge = row.css_first("a.custom-pos-badge")

        if not name_div or not pos_badge:
            continue

        # OVR is reliably stored in data-sort-value on the stat td
        # (the inner span may contain delta indicators concatenated with the number).
        ovr_str = ovr_td.attributes.get("data-sort-value", "")
        try:
            ovr = int(ovr_str)
        except ValueError:
            continue

        player_name = name_div.text(strip=True)
        position = pos_badge.text(strip=True)

        if not player_name or not position:
            continue

        # Club link text; None when missing.
        club_link = row.css_first("a.custom-roster-team")
        club: Optional[str] = (club_link.text(strip=True) or None) if club_link else None

        # Defensively handle compound positions like "RW/RM".
        primary_position = position.split("/")[0]
        alt_raw = position.split("/")[1:] if "/" in position else []
        alt_positions: tuple[str, ...] = tuple(alt_raw)

        card_id = make_card_id(player_name, "base")
        # duplicate ids are possible if two players share a romanized name;
        # the repository upsert layer resolves collisions (last write wins)

        cards.append(
            Card(
                id=card_id,
                player_name=player_name,
                version="base",
                ovr=ovr,
                position=primary_position,
                alt_positions=alt_positions,
                club=club,
                source_url=source_url,
                crawled_at=today,
            )
        )

    if len(cards) < _MIN_CARDS:
        raise ParseError(
            f"fcratings page {source_url} yielded only {len(cards)} cards "
            f"- layout changed?"
        )

    return cards


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


def fetch_top100(
    url: str = "https://www.fcratings.com/lists/top-100-players",
) -> list[Card]:
    """Fetch and parse the fcratings top-100 list page.

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
            return parse_top100_page(response.text, source_url=url)
        except httpx.HTTPError as exc:
            last_error = exc

    raise FetchError(f"could not fetch {url}: {last_error}")
