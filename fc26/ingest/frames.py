"""HD card backgrounds from futbin - one detail-page fetch per distinct frame.

Every card of a type shares one background (all gold cards, all Base Heroes...),
and futbin names the frame file after the type (``cards/tiny/72_base_hero.png``).
So instead of one detail page per card (images.py), fetch ONE representative
card's detail page per frame and apply its HD ``bg_url`` to the whole group:
a handful of requests for the entire pool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from ..db import CardRepository
from ..errors import FC26Error, RateLimitedError
from ..models import Card
from .images import parse_player_art

_FUTBIN_FRAME_RE = re.compile(r"/cards/(tiny|hd)/([^/?]+)\.png")
_FUTGG_FRAME_RE = re.compile(r"/rarities-level-\d+-large/(\d+)\.")
MAX_TRIES_PER_FRAME = 3       # representatives to try before reporting the frame missed


@dataclass(frozen=True)
class FramesResult:
    frames: tuple[str, ...]       # frame names upgraded to HD
    cards: int                    # cards whose bg_url changed
    missed: tuple[str, ...]       # "frame: reason"


def _futbin_frame(url: str | None) -> tuple[str, bool] | None:
    """(frame name, is_hd) of a futbin card-background URL."""
    match = _FUTBIN_FRAME_RE.search(url or "")
    return (match.group(2), match.group(1) == "hd") if match else None


def frame_of(card: Card, known: set[str]) -> str | None:
    """The futbin frame name for a card; a fut.gg frame maps over by rarity id."""
    own = _futbin_frame(card.bg_url)
    if own:
        return own[0]
    rarity = _FUTGG_FRAME_RE.search(card.bg_url or "")
    if rarity:
        named = [k for k in known if k.split("_", 1)[0] == rarity.group(1)]
        return named[0] if len(named) == 1 else None
    return None


def upgrade_card_frames(
    repo: CardRepository,
    *,
    fetch_html: Callable[[str], str],
    sleep: Callable[[float], None],
    delay: float = 2.0,
    on_progress: Callable[[str], None] = lambda _msg: None,
) -> FramesResult:
    cards = repo.find_all()
    known = {f[0] for c in cards if (f := _futbin_frame(c.bg_url))}
    groups: dict[str, list[Card]] = {}
    for card in cards:
        frame = frame_of(card, known)
        if frame:
            groups.setdefault(frame, []).append(card)

    done: list[str] = []
    missed: list[str] = []
    changed = 0
    for frame, members in sorted(groups.items()):
        hd_url = next((c.bg_url for c in members if _futbin_frame(c.bg_url) == (frame, True)), None)
        reason = "no card with a futbin_url"
        if hd_url is None:
            # representatives: cards still showing this exact futbin frame, best first
            reps = [c for c in members if c.futbin_url and _futbin_frame(c.bg_url)]
            for rep in sorted(reps, key=lambda c: -c.ovr)[:MAX_TRIES_PER_FRAME]:
                try:
                    art = parse_player_art(fetch_html(rep.futbin_url))
                except RateLimitedError:
                    raise
                except FC26Error as exc:
                    reason = str(exc)
                    continue
                finally:
                    sleep(delay)
                if _futbin_frame(art.bg_url) == (frame, True):
                    hd_url = art.bg_url
                    break
                reason = f"{rep.id} page shows {_futbin_frame(art.bg_url)}, expected {frame}"
        if hd_url is None:
            missed.append(f"{frame}: {reason}")
            continue
        for card in members:
            if card.bg_url != hd_url:
                repo.upsert(replace(card, bg_url=hd_url))
                changed += 1
        done.append(frame)
        on_progress(f"frame {frame}: {len(members)} cards")
    return FramesResult(tuple(done), changed, tuple(missed))
