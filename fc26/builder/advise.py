"""Strategy advisor: read-only, actionable tips for a squad.

Pure analysis over existing primitives (no new model). Diagnoses where the
chemistry is leaking and where the cheapest gains are; `plan`/`upgrade` act on
the findings.

- tier leverage: club/league/nation groups one or two contributors short of
  their next chem tier (lifts every sharer at once)
- out of position: players whose slot position differs from their card's,
  earning 0 chem
- weakest slots: the lowest pace-meta players, i.e. the first upgrade targets
- best chem style: per outfield slot, the style that most raises pace-meta at
  that slot's current chem level
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..chem.engine import compute_chemistry
from ..chem.lineup import Lineup
from ..chem.styles import available_styles
from ..models import Card
from .boost import boosted_stats
from .meta import meta_score

WEAKEST_SLOTS = 3   # number of low-meta upgrade targets to surface


@dataclass(frozen=True)
class TierLeverage:
    kind: str           # "club" | "league" | "nation"
    name: str
    count: int
    points: int
    needed: int         # more in-position contributors to reach the next tier


@dataclass(frozen=True)
class SlotNote:
    slot: str
    player_name: str
    position: str
    meta: float | None
    chem: int
    reason: str


@dataclass(frozen=True)
class StyleAdvice:
    slot: str
    player_name: str
    chem: int
    recommended_style: str | None
    meta_gain: float                # boosted meta - base meta (0.0 when no pick)
    note: str | None


@dataclass(frozen=True)
class Advice:
    formation: str
    team_chem: int
    tier_leverage: tuple[TierLeverage, ...]
    out_of_position: tuple[SlotNote, ...]
    weakest_slots: tuple[SlotNote, ...]
    style_advice: tuple[StyleAdvice, ...]
    summary: tuple[str, ...]
    warnings: tuple[str, ...]


def _best_style(card: Card, position: str, chem: int) -> tuple[str | None, float]:
    """(style, meta_gain) maximising pace-meta at this chem level, else (None, 0)."""
    base = meta_score(card, position)
    if base is None:
        return None, 0.0
    best_style: str | None = None
    best_meta = base
    for style in available_styles():
        boosted = boosted_stats(card, style, chem)
        cand = meta_score(replace(card, face=boosted.face), position)
        if cand is not None and cand > best_meta:
            best_meta = cand
            best_style = style
    return best_style, best_meta - base


def _style_advice(slot: str, card: Card, position: str, chem: int) -> StyleAdvice:
    if position == "GK":
        return StyleAdvice(slot, card.player_name, chem, None, 0.0, "GK - style advice n/a")
    if meta_score(card, position) is None:
        return StyleAdvice(slot, card.player_name, chem, None, 0.0, "missing face stats")
    if chem <= 0:
        return StyleAdvice(slot, card.player_name, chem, None, 0.0, "0 chem - style inert")
    style, gain = _best_style(card, position, chem)
    note = None if style else "no style raises pace-meta"
    return StyleAdvice(slot, card.player_name, chem, style, gain, note)


def _summary(
    team_chem: int,
    leverage: list[TierLeverage],
    oop: list[SlotNote],
    weakest: tuple[SlotNote, ...],
    styles: list[StyleAdvice],
) -> tuple[str, ...]:
    lines = [f"team chemistry {team_chem}/33"]
    if oop:
        names = ", ".join(f"{n.slot} ({n.player_name})" for n in oop)
        lines.append(f"{len(oop)} out of position, 0 chem: {names}")
    if leverage:
        top = leverage[0]
        lines.append(f"closest chem gain: +{top.needed} more {top.kind} "
                     f"({top.name}) reaches the next tier")
    if weakest:
        w = weakest[0]
        lines.append(f"weakest slot: {w.slot} {w.player_name} (meta {w.meta:.0f})")
    picks = [s for s in styles if s.recommended_style]
    if picks:
        best = max(picks, key=lambda s: s.meta_gain)
        lines.append(f"best style pick: {best.recommended_style} on {best.slot} "
                     f"(+{best.meta_gain:.1f} meta)")
    return tuple(lines)


def advise_squad(lineup: Lineup, slot_cards: dict[str, Card]) -> Advice:
    report = compute_chemistry(lineup, slot_cards)

    leverage = sorted(
        (TierLeverage(t.kind, t.name, t.count, t.points, t.next_tier_at - t.count)
         for t in report.tiers if t.next_tier_at is not None),
        key=lambda lv: (lv.needed, lv.kind, lv.name),
    )

    oop: list[SlotNote] = []
    rated: list[SlotNote] = []
    styles: list[StyleAdvice] = []
    for p in report.players:
        card = slot_cards[p.slot]
        meta = meta_score(card, p.position)
        if not p.in_position:
            oop.append(SlotNote(p.slot, p.player_name, p.position, meta, p.chem,
                                f"plays {card.position}, not {p.position} - 0 chem"))
        if meta is not None:
            rated.append(SlotNote(p.slot, p.player_name, p.position, meta, p.chem, ""))
        styles.append(_style_advice(p.slot, card, p.position, p.chem))

    weakest = tuple(sorted(rated, key=lambda n: n.meta)[:WEAKEST_SLOTS])
    summary = _summary(report.team_total, leverage, oop, weakest, styles)

    return Advice(
        formation=lineup.formation,
        team_chem=report.team_total,
        tier_leverage=tuple(leverage),
        out_of_position=tuple(oop),
        weakest_slots=weakest,
        style_advice=tuple(styles),
        summary=summary,
        warnings=report.warnings,
    )
