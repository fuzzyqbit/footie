"""PlayStyles, sub-stats and HD card art for futbin-sourced cards, from fut.gg card pages.

futbin list rows (expand.py) carry no PlayStyles or sub-stats. Rather than fetch
every futbin detail page, this pass reads the matching fut.gg card page. The two
sites are joined exactly, not by name: futbin's player image is named after the
card's EA item id (``.../players/p84039159.png``) and fut.gg card URLs are
``/players/<base id>/27-<item id>/`` (the slug is optional - fut.gg redirects),
where the base player id is the low 24 bits of the item id.

Each page is verified (item id + overall) before anything is written, so a wrong
join can never overwrite a card with another player's data.

Fallback: futbin sometimes names the image after the BASE player id even though
the card's item id differs (id + n * 2**24), so the direct URL 404s. We then read
the player's fut.gg hub page, fetch their FC cards of this game year, and accept
one only when exactly one has the card's overall - ambiguity is a miss, never a guess.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, replace
from typing import Callable

from ..db import CardRepository
from ..errors import FC26Error, RateLimitedError
from ..models import Card
from .futgg import _extract_playstyles, _extract_subs

GAME_YEAR = 27
FUTGG_CARD_URL = "https://www.fut.gg/players/{base_id}/{year}-{ea_id}/"
FUTGG_PLAYER_URL = "https://www.fut.gg/players/{base_id}/"
MAX_HUB_CANDIDATES = 6        # a player's FC cards to try before giving up
CHUNK_SIZE = 25               # cards per batched write - bounds work lost on interrupt

# futbin: .../players/p84039159.png   fut.gg: .../player-item/27-84039159.<hash>.webp
_EA_ID_RE = re.compile(r"/players/p?(\d+)\.png|/player-item/\d+-(\d+)\.")
# fut.gg's public image CDN resizes on the fly; paths come from the card's JS blob.
FUTGG_IMAGE_URL = "https://game-assets.fut.gg/cdn-cgi/image/quality=85,format=auto,width={width}/{path}"
PLAYER_WIDTH = 256            # source cut-outs are ~160px; no gain asking for more
FRAME_WIDTH = 512
_PLAYER_PATH_RE = re.compile(r'\bimagePath:"(\d{4}/player-item/[^"]+)"')
_FRAME_PATH_RE = re.compile(r'\bimagePath:"(\d{4}/rarities-level-\d+-large/[^"]+)"')
_PAGE_EA_ID_RE = re.compile(r"\beaId:(\d+),evolutionId:")
_PAGE_OVERALL_RE = re.compile(r"\boverall:(\d{2})\b")


@dataclass(frozen=True)
class StylesResult:
    updated: tuple[str, ...]
    skipped: tuple[str, ...]      # already has sub-stats + HD art, or no EA id to join on
    missed: tuple[str, ...]       # "id: reason"


def ea_item_id(card: Card) -> int | None:
    """The card's EA item id, recovered from its futbin player-image URL."""
    match = _EA_ID_RE.search(card.image_url or "")
    return int(match.group(1) or match.group(2)) if match else None


def futgg_url_for(card: Card) -> str | None:
    ea_id = ea_item_id(card)
    if ea_id is None:
        return None
    return FUTGG_CARD_URL.format(base_id=ea_id & 0xFFFFFF, year=GAME_YEAR, ea_id=ea_id)


def has_futgg_art(card: Card) -> bool:
    return "game-assets.fut.gg" in (card.image_url or "")


def _extract_art(html: str) -> tuple[str | None, str | None]:
    """(player cut-out URL, card frame URL) for the page's main card, from its JS blob."""
    page_id = _PAGE_EA_ID_RE.search(html)
    blob = html[page_id.start():] if page_id else html
    player = _PLAYER_PATH_RE.search(blob)
    frame = _FRAME_PATH_RE.search(blob)
    return (
        FUTGG_IMAGE_URL.format(width=PLAYER_WIDTH, path=player.group(1)) if player else None,
        FUTGG_IMAGE_URL.format(width=FRAME_WIDTH, path=frame.group(1)) if frame else None,
    )


def _verify(html: str, card: Card, ea_id: int) -> str | None:
    """Reason the page is NOT this card, or None when it checks out."""
    page_id = _PAGE_EA_ID_RE.search(html)
    if page_id is None or int(page_id.group(1)) != ea_id:
        return f"page is item {page_id.group(1) if page_id else '?'}, expected {ea_id}"
    overall = _PAGE_OVERALL_RE.search(html[page_id.start():])
    if overall is None or int(overall.group(1)) != card.ovr:
        return f"page overall {overall.group(1) if overall else '?'} != card {card.ovr}"
    return None


async def _find_via_player_hub(fetcher, card: Card, base_id: int) -> tuple[int, str] | None:
    """(item id, page html) of the player's single card with this overall, else None."""
    hub = await fetcher.fetch(FUTGG_PLAYER_URL.format(base_id=base_id))
    item_ids = list(dict.fromkeys(
        int(i) for i in re.findall(rf'href="/players/{base_id}[^"/]*/{GAME_YEAR}-(\d+)/?"', hub)
    ))
    matches: list[tuple[int, str]] = []
    for item_id in item_ids[:MAX_HUB_CANDIDATES]:
        html = await fetcher.fetch(
            FUTGG_CARD_URL.format(base_id=base_id, year=GAME_YEAR, ea_id=item_id))
        if _verify(html, card, item_id) is None:
            matches.append((item_id, html))
    return matches[0] if len(matches) == 1 else None


async def upgrade_card_styles_async(
    repo: CardRepository,
    *,
    fetcher,
    on_progress: Callable[[str], None] = lambda _msg: None,
    refresh: bool = False,
    limit: int | None = None,
) -> StylesResult:
    """Fill playstyles / playstyles_plus / subs from fut.gg for cards lacking sub-stats.

    Writes in CHUNK_SIZE batches so an interrupted or rate-limited run keeps its
    progress; rerun to continue (finished cards are skipped).
    """
    updated: list[str] = []
    skipped: list[str] = []
    missed: list[str] = []
    todo: list[tuple[Card, int, str]] = []
    for card in repo.find_all():
        url = futgg_url_for(card)
        done = card.subs is not None and has_futgg_art(card)
        if url is None or (done and not refresh):
            skipped.append(card.id)
            continue
        todo.append((card, ea_item_id(card), url))
    todo.sort(key=lambda item: item[0].subs is not None)   # missing stats first, art-only after
    if limit is not None:
        todo = todo[:limit]

    async def _fetch(card: Card, ea_id: int, url: str):
        try:
            return card, ea_id, await fetcher.fetch(url), None
        except RateLimitedError as exc:
            return card, ea_id, None, exc
        except FC26Error as exc:
            try:
                found = await _find_via_player_hub(fetcher, card, ea_id & 0xFFFFFF)
            except FC26Error as hub_exc:
                return card, ea_id, None, hub_exc
            if found is None:
                return card, ea_id, None, exc
            return card, found[0], found[1], None

    for start in range(0, len(todo), CHUNK_SIZE):
        results = await asyncio.gather(*(_fetch(*item) for item in todo[start : start + CHUNK_SIZE]))
        blocked = next((exc for *_, exc in results if isinstance(exc, RateLimitedError)), None)
        with repo.batch():
            for card, ea_id, html, exc in results:
                if isinstance(exc, RateLimitedError):
                    continue          # not fetched yet - picked up on the next run
                if exc is not None:
                    missed.append(f"{card.id}: {exc}")
                    continue
                problem = _verify(html, card, ea_id)
                subs = _extract_subs(html) if problem is None else None
                if problem is None and subs is None:
                    problem = "no sub-stats on page - fut.gg layout changed?"
                if problem is not None:
                    missed.append(f"{card.id}: {problem}")
                    continue
                playstyles, playstyles_plus = _extract_playstyles(html)
                # player cut-out only: backgrounds come from futbin (frames.py)
                image_url, _frame = _extract_art(html)
                repo.upsert(replace(card, subs=subs, playstyles=playstyles,
                                    playstyles_plus=playstyles_plus,
                                    image_url=image_url or card.image_url))
                updated.append(card.id)
        on_progress(f"styles: {len(updated)} updated, {len(missed)} missed "
                    f"({min(start + CHUNK_SIZE, len(todo))}/{len(todo)})")
        if blocked is not None:
            raise RateLimitedError(
                f"{blocked} ({len(updated)} updated before the block - rerun to continue)",
                blocked.retry_after,
            )

    return StylesResult(tuple(updated), tuple(skipped), tuple(missed))
