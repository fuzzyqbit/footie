"""Per-position meta scoring: pace-meta-weighted face stats.

Weights mirror the playbook's identity (docs/02) and pace doctrine (docs/09):
wide players and fullbacks prize PAC, strikers PAC+SHO, CBs DEF/PHY/PAC.
Tune here; every row must sum to 1.0 (unit-tested).
"""

from __future__ import annotations

from ..models import Card

CHEM_WEIGHT = 3.0   # squad_score = sum(meta) + CHEM_WEIGHT * team_chem

# "rating" objective: maximise raw squad OVR; chem only breaks ties so a
# higher-rated XI always wins but chem is preferred among equal-OVR options.
RATING_CHEM_WEIGHT = 0.1

VALID_OBJECTIVES = ("meta", "rating")

# position -> (pac, sho, pas, dri, def_, phy); each row sums to 1.0
META_WEIGHTS: dict[str, tuple[float, float, float, float, float, float]] = {
    "ST":  (.30, .35, .05, .20, .00, .10),
    "CF":  (.15, .25, .25, .25, .00, .10),
    "CAM": (.15, .25, .25, .25, .00, .10),
    "RW":  (.35, .20, .15, .25, .00, .05),
    "LW":  (.35, .20, .15, .25, .00, .05),
    "RM":  (.35, .20, .15, .25, .00, .05),
    "LM":  (.35, .20, .15, .25, .00, .05),
    "CM":  (.15, .15, .25, .20, .15, .10),
    "CDM": (.10, .05, .20, .15, .30, .20),
    "RB":  (.30, .05, .10, .15, .25, .15),
    "LB":  (.30, .05, .10, .15, .25, .15),
    "RWB": (.30, .05, .10, .15, .25, .15),
    "LWB": (.30, .05, .10, .15, .25, .15),
    "CB":  (.25, .03, .07, .05, .35, .25),
    # GK face slots hold DIV/HAN/KIC/REF/SPD/POS (phase-2 mapping)
    "GK":  (.25, .20, .05, .30, .05, .15),
}


def meta_score(card: Card, position: str) -> float | None:
    """Weighted face-stat score on the 0-99 scale; None if any face stat missing."""
    weights = META_WEIGHTS[position]
    stats = (card.face.pac, card.face.sho, card.face.pas,
             card.face.dri, card.face.def_, card.face.phy)
    if any(stat is None for stat in stats):
        return None
    return sum(weight * stat for weight, stat in zip(weights, stats))
