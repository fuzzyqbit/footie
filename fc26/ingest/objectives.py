"""Scrape fut.gg objective reward players + task text and match them to cards.

The objectives hub (https://www.fut.gg/objectives/) is server-rendered HTML with
no __NEXT_DATA__ / no JSON API: everything lives in the DOM. The hub and its
category pages contain anchor links ``a[href^='/objectives/']`` to leaf objective
pages. On a leaf page:

- the ``<h1>`` is the objective group name (e.g. "USA - EA SPORTS FC 26 Objectives"),
- reward player names appear as ``<img alt="Player Name">`` (alongside noise alts
  like "Tokens" / "Player Pick" / pack names, which never match a real card name),
- the human-readable task lines live in ``<p class="text-sm text-gray-300">`` rows.

We match reward player names to UNTRADEABLE cards (``card.price is None``) by folded
name, and attach the page's task text. Task text is only ever real scraped data;
if a page has no parseable tasks we store an empty list (we never fabricate text).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Iterable

import httpx
from selectolax.parser import HTMLParser

from ..db import CardRepository
from ..known_names import fold

HUB_URL = "https://www.fut.gg/objectives/"
BASE_URL = "https://www.fut.gg"

# fut.gg blocks the repo's default UA but serves a normal browser UA fine.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT_SECONDS = 20

# Hub-level / non-leaf links that hold no reward players of their own.
SKIP_PATHS = {
    "/objectives/",
    "/objectives/expiring-soon/",
    "/objectives/expiring-soon",
    "/objectives/coming-soon/",
    "/objectives/coming-soon",
}

# Strip a leading numeric id and the EA SPORTS suffix from the h1 group name.
_LEADING_ID_RE = re.compile(r"^\d+\s*")
_SUFFIX_RE = re.compile(r"\s*-?\s*EA SPORTS FC 26 Objectives\s*$", re.IGNORECASE)


def default_fetch_html(url: str) -> str:
    """GET a fut.gg page with a browser UA (1 retry), or raise httpx.HTTPError."""
    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = httpx.get(
                url,
                timeout=TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={"User-Agent": BROWSER_UA},
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
    raise httpx.RequestError(f"could not fetch {url}: {last_error}")


def clean_group_name(raw: str | None) -> str:
    """Strip leading numeric id + EA SPORTS suffix; fall back to 'Objectives'."""
    if not raw:
        return "Objectives"
    name = _SUFFIX_RE.sub("", raw)
    name = _LEADING_ID_RE.sub("", name).strip()
    return name or "Objectives"


def _absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE_URL + href


def collect_objective_links(hub_html: str) -> list[str]:
    """Return absolute URLs of objective category/leaf pages from a hub page.

    De-duplicated, hub/expiring/coming-soon index links excluded.
    """
    tree = HTMLParser(hub_html)
    seen: set[str] = set()
    ordered: list[str] = []
    for a in tree.css("a[href^='/objectives/']"):
        href = (a.attributes.get("href") or "").split("?")[0].split("#")[0]
        if not href or href in SKIP_PATHS:
            continue
        url = _absolute(href)
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def extract_player_alts(page_html: str) -> list[str]:
    """Return all non-empty ``<img alt>`` strings on a page (noise included).

    Noise alts (Tokens, Player Pick, pack names, Logo) are harmless: they simply
    won't fold-match any real card name downstream.
    """
    tree = HTMLParser(page_html)
    alts: list[str] = []
    for img in tree.css("img[alt]"):
        alt = (img.attributes.get("alt") or "").strip()
        if alt:
            alts.append(alt)
    return alts


def extract_tasks(page_html: str) -> list[str]:
    """Return real task/requirement lines from an objective leaf page.

    Tasks render as ``<p class="text-sm text-gray-300">`` rows inside each
    objective card. We return them de-duplicated and in document order. If a
    page has no such rows (e.g. a category index) we return an empty list -
    we never invent text.
    """
    tree = HTMLParser(page_html)
    tasks: list[str] = []
    seen: set[str] = set()
    for p in tree.css("p.text-gray-300"):
        text = " ".join(p.text().split())
        if text and text not in seen:
            seen.add(text)
            tasks.append(text)
    return tasks


def scrape_objectives(
    fetch_html: Callable[[str], str] = default_fetch_html,
    hub_url: str = HUB_URL,
) -> list[dict]:
    """Crawl the objectives hub and every leaf page.

    Returns one record per fetched page:
    ``{"url": str, "group": str, "player_alts": [str], "tasks": [str]}``.
    Pages that fail to fetch are skipped silently (best-effort crawl).
    """
    hub_html = fetch_html(hub_url)
    links = collect_objective_links(hub_html)

    pages: list[dict] = []
    for url in links:
        try:
            html = fetch_html(url)
        except httpx.HTTPError:
            continue
        tree = HTMLParser(html)
        h1 = tree.css_first("h1")
        group = clean_group_name(h1.text().strip() if h1 else None)
        pages.append(
            {
                "url": url,
                "group": group,
                "player_alts": extract_player_alts(html),
                "tasks": extract_tasks(html),
            }
        )
    return pages


def build_objectives(
    repo: CardRepository,
    fetch_html: Callable[[str], str] = default_fetch_html,
    hub_url: str = HUB_URL,
    pages: Iterable[dict] | None = None,
) -> list[dict]:
    """Match reward players to UNTRADEABLE cards and attach task text.

    A card is eligible only when ``card.price is None`` (untradeable). For each
    page, every ``<img alt>`` whose folded text equals an eligible card's folded
    ``player_name`` produces a match record::

        {card_id, player_name, objective, source_url, tasks: [str, ...]}

    Results are de-duplicated by (card_id, source_url) and sorted by card_id.
    """
    if pages is None:
        pages = scrape_objectives(fetch_html=fetch_html, hub_url=hub_url)

    # folded player_name -> list of untradeable cards
    by_folded: dict[str, list] = {}
    for card in repo.find_all():
        if card.price is None:
            by_folded.setdefault(fold(card.player_name), []).append(card)

    results: dict[tuple[str, str], dict] = {}
    for page in pages:
        url = page["url"]
        group = page["group"]
        tasks = list(page.get("tasks") or [])
        matched_folded: set[str] = set()
        for alt in page.get("player_alts", []):
            folded = fold(alt)
            if folded in matched_folded:
                continue
            cards = by_folded.get(folded)
            if not cards:
                continue
            matched_folded.add(folded)
            for card in cards:
                key = (card.id, url)
                if key in results:
                    continue
                results[key] = {
                    "card_id": card.id,
                    "player_name": card.player_name,
                    "objective": group,
                    "source_url": url,
                    "tasks": tasks,
                }
    return sorted(results.values(), key=lambda r: (r["card_id"], r["source_url"]))


def write_objectives(
    path: Path | str,
    repo: CardRepository,
    fetch_html: Callable[[str], str] = default_fetch_html,
    hub_url: str = HUB_URL,
) -> list[dict]:
    """Scrape, match, and write the objectives list to JSON. Returns the list."""
    records = build_objectives(repo, fetch_html=fetch_html, hub_url=hub_url)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records
