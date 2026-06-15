"""Scrape fut.gg SBC sets (cost, rewards, repeatability) and rank the best ones.

fut.gg SBC pages (https://www.fut.gg/sbc/) are Next.js Server Components: there is
NO ``__NEXT_DATA__`` JSON blob to parse. The structured data instead lives in an
RSC (React Server Component) payload embedded in the HTML as JS-ish object
literals - booleans render as ``!0`` / ``!1`` and shared values are hoisted into
``$R[n]=`` references. So we extract fields with plain regex over the raw HTML
text, never a JSON parser.

Crawl shape:

- The hub links to category index pages ``/sbc/category/<cat>/`` and to leaf SBC
  pages ``/sbc/<category>/<id-slug>/`` (e.g. ``/sbc/upgrades/26-1014-3x-87-90-upgrade/``).
- We gather leaf links from the hub AND from each category index page, union them
  de-duplicated, and fetch each leaf to build one record per SBC set.

On a leaf page the set object reads roughly::

    slug:"26-1014-3x-87-90-upgrade",categoryEaId:2,name:"3x 87-90 Upgrade",
    description:"Earn a pack...",...cheapestSolutionPrice:5850...
    pack:"3x 87-90 Rare Gold Players Pack"...isRepeatable:!0,numberOfRepeats:3

The ``cost`` we report is the SUM of every sub-challenge's ``cheapestSolutionPrice``
(fut.gg's live cheapest-console solution price) found on the page. It is real
scraped market data - we never fabricate a cost. If a sub-challenge has no priced
solution (``cheapestSolutionPrice:null`` / absent) we flag ``cost_complete=False``
and simply don't add it; if NO sub-challenge has a price we report ``cost=null``.

Ranking surfaces pack/value SBCs (cheap repeatable upgrades) ahead of one-off
player SBCs via a transparent category-priority heuristic - we invent no EV/profit
numbers, we only order by category, repeatability, then real cost.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import httpx
from selectolax.parser import HTMLParser

HUB_URL = "https://www.fut.gg/sbc/"
BASE_URL = "https://www.fut.gg"

# fut.gg blocks the repo's default UA but serves a normal browser UA fine.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT_SECONDS = 20

# Strip a leading numeric id + the EA SPORTS suffix from the <h1> fallback name.
_LEADING_ID_RE = re.compile(r"^\d+\s*")
_SUFFIX_RE = re.compile(r"\s*-?\s*EA SPORTS FC 26 SBC\s*$", re.IGNORECASE)

# Leaf-page field regexes over the raw RSC payload (JS object literals).
_NAME_RE = re.compile(r'slug:"([^"]+)",categoryEaId:\d+,name:"([^"]+)"')
_DESC_RE = re.compile(r'name:"[^"]+",description:"([^"]*)"')
_PRICE_RE = re.compile(r"cheapestSolutionPrice:(\d+|null)")
_PRICE_PC_RE = re.compile(r"cheapestSolutionPricePc:(\d+|null)")
_PACK_RE = re.compile(r'pack:"([^"]+)"')
_PLAYER_EA_ID_RE = re.compile(r"playerEaId:(\d+|null)")
_REPEATABLE_RE = re.compile(r"isRepeatable:(!0|!1)")
_REPEATS_RE = re.compile(r"numberOfRepeats:(\d+)")
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

# Leaf URL: /sbc/<category>/<slug>/ where <category> != "category".
_LEAF_PATH_RE = re.compile(r"^/sbc/(?!category/)([^/]+)/([^/]+)/?$")
_HREF_RE = re.compile(r'href="(/sbc/[^"#?]*)')

# Ranking: pack/value SBCs first, unknown categories last.
CATEGORY_PRIORITY = {
    "upgrades": 0,
    "challenges": 1,
    "players": 2,
    "icons": 3,
    "swaps": 4,
    "foundations": 5,
}
_UNKNOWN_CATEGORY_RANK = 99


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


def clean_set_name(raw: str | None) -> str:
    """Strip leading numeric id + EA SPORTS FC 26 SBC suffix from an h1 name."""
    if not raw:
        return "SBC"
    name = _SUFFIX_RE.sub("", raw)
    name = _LEADING_ID_RE.sub("", name).strip()
    return name or "SBC"


def _absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE_URL + href


def _is_leaf(href: str) -> bool:
    return bool(_LEAF_PATH_RE.match(href))


def _is_category(href: str) -> bool:
    return href.startswith("/sbc/category/")


def _hrefs(html: str) -> list[str]:
    """Return de-duplicated /sbc/ hrefs (query/hash stripped) in document order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for href in _HREF_RE.findall(html):
        href = href.split("?")[0].split("#")[0]
        if href and href not in seen:
            seen.add(href)
            ordered.append(href)
    return ordered


def collect_sbc_leaf_links(hub_html: str, base_url: str = BASE_URL) -> list[str]:
    """Return absolute leaf SBC URLs linked directly from the hub page.

    Leaf pages are ``/sbc/<category>/<slug>/`` with ``category != "category"``;
    the hub itself, ``/sbc/``, and ``/sbc/category/...`` index links are excluded.
    """
    ordered: list[str] = []
    for href in _hrefs(hub_html):
        if _is_leaf(href):
            ordered.append(base_url + href if not href.startswith("http") else href)
    return ordered


def collect_category_links(hub_html: str) -> list[str]:
    """Return absolute ``/sbc/category/<cat>/`` index URLs linked from the hub."""
    ordered: list[str] = []
    for href in _hrefs(hub_html):
        if _is_category(href):
            ordered.append(_absolute(href))
    return ordered


def collect_leaf_links_from_category(category_html: str) -> list[str]:
    """Return absolute leaf SBC URLs found on a category index page."""
    return collect_sbc_leaf_links(category_html)


def _unescape(raw: str) -> str:
    """Minimally unescape an RSC string literal (\\u escapes + \\" \\\\ \\/)."""
    if not raw:
        return raw
    text = re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        raw,
    )
    return text.replace('\\"', '"').replace("\\\\", "\\").replace("\\/", "/")


def _category_from_url(url: str) -> str:
    match = re.search(r"/sbc/([^/]+)/", url)
    if match and match.group(1) != "category":
        return match.group(1)
    return ""


def parse_sbc(leaf_html: str, url: str) -> dict:
    """Parse a single leaf SBC page into a record (pure: html + url only).

    All fields come from regex over the raw RSC payload; cost is the summed live
    ``cheapestSolutionPrice`` across sub-challenges (never fabricated).
    """
    category = _category_from_url(url)

    name_match = _NAME_RE.search(leaf_html)
    if name_match:
        slug = name_match.group(1)
        name = _unescape(name_match.group(2))
    else:
        slug = ""
        h1 = _H1_RE.search(leaf_html)
        h1_text = _TAG_RE.sub("", h1.group(1)).strip() if h1 else None
        name = clean_set_name(h1_text)
    if not slug:
        slug_match = re.search(r"/sbc/[^/]+/([^/]+)/?$", url)
        slug = slug_match.group(1) if slug_match else ""

    desc_match = _DESC_RE.search(leaf_html)
    description = _unescape(desc_match.group(1)) if desc_match else ""

    # Console cost: sum numeric prices; flag incomplete if any sub-challenge null.
    cost: int | None = 0
    cost_complete = True
    price_tokens = _PRICE_RE.findall(leaf_html)
    numeric_prices = [int(p) for p in price_tokens if p != "null"]
    if any(p == "null" for p in price_tokens):
        cost_complete = False
    if numeric_prices:
        cost = sum(numeric_prices)
    else:
        cost = None
        if price_tokens:  # there were challenges, all unpriced
            cost_complete = False

    pc_prices = [int(p) for p in _PRICE_PC_RE.findall(leaf_html) if p != "null"]
    cost_pc: int | None = sum(pc_prices) if pc_prices else None

    reward_packs: list[str] = []
    for pack in _PACK_RE.findall(leaf_html):
        pack = _unescape(pack)
        if pack and pack not in reward_packs:
            reward_packs.append(pack)

    reward_player_ea_ids = [
        int(pid) for pid in _PLAYER_EA_ID_RE.findall(leaf_html) if pid != "null"
    ]
    # De-duplicate player ea ids, preserving order.
    seen_ids: set[int] = set()
    reward_player_ea_ids = [
        pid for pid in reward_player_ea_ids
        if not (pid in seen_ids or seen_ids.add(pid))
    ]

    repeat_match = _REPEATABLE_RE.search(leaf_html)
    repeatable = repeat_match.group(1) == "!0" if repeat_match else False
    repeats_match = _REPEATS_RE.search(leaf_html)
    number_of_repeats = int(repeats_match.group(1)) if repeats_match else None

    return {
        "slug": slug,
        "name": name,
        "category": category,
        "description": description,
        "cost": cost,
        "cost_complete": cost_complete,
        "cost_pc": cost_pc,
        "reward_packs": reward_packs,
        "reward_player_ea_ids": reward_player_ea_ids,
        "repeatable": repeatable,
        "number_of_repeats": number_of_repeats,
        "source_url": url,
    }


def scrape_sbcs(
    fetch_html: Callable[[str], str] = default_fetch_html,
    hub_url: str = HUB_URL,
) -> list[dict]:
    """Crawl the SBC hub + category index pages and parse every leaf SBC.

    Returns one record per leaf page (see ``parse_sbc``). Pages that fail to
    fetch are skipped silently (best-effort crawl).
    """
    hub_html = fetch_html(hub_url)

    seen: set[str] = set()
    leaf_urls: list[str] = []
    for url in collect_sbc_leaf_links(hub_html):
        if url not in seen:
            seen.add(url)
            leaf_urls.append(url)

    for category_url in collect_category_links(hub_html):
        try:
            category_html = fetch_html(category_url)
        except httpx.HTTPError:
            continue
        for url in collect_leaf_links_from_category(category_html):
            if url not in seen:
                seen.add(url)
                leaf_urls.append(url)

    records: list[dict] = []
    for url in leaf_urls:
        try:
            leaf_html = fetch_html(url)
        except httpx.HTTPError:
            continue
        records.append(parse_sbc(leaf_html, url))
    return records


def rank_key(record: dict) -> tuple:
    """Sort key surfacing pack/value SBCs first (transparent heuristic).

    Primary: category priority (upgrades, challenges, players, icons, swaps,
    foundations, then unknown). Secondary: repeatable before non-repeatable.
    Tertiary: ascending cost (null cost sinks via +infinity).
    """
    category_rank = CATEGORY_PRIORITY.get(record.get("category", ""), _UNKNOWN_CATEGORY_RANK)
    repeatable_rank = 0 if record.get("repeatable") else 1
    cost = record.get("cost")
    cost_rank = cost if isinstance(cost, int) else float("inf")
    return (category_rank, repeatable_rank, cost_rank)


def build_sbcs(
    fetch_html: Callable[[str], str] = default_fetch_html,
    hub_url: str = HUB_URL,
) -> list[dict]:
    """Scrape every SBC and return them rank-sorted (best/most useful first)."""
    records = scrape_sbcs(fetch_html=fetch_html, hub_url=hub_url)
    return sorted(records, key=rank_key)


def write_sbcs(
    path: Path | str,
    fetch_html: Callable[[str], str] = default_fetch_html,
    hub_url: str = HUB_URL,
) -> list[dict]:
    """Scrape, rank, and write the SBC list to JSON. Returns the list."""
    records = build_sbcs(fetch_html=fetch_html, hub_url=hub_url)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records
