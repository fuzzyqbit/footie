"""Standard formation definitions (slot keys in pitch order, GK first).

Slot keys are position codes with numeric suffixes for duplicates (CB1/CB2);
a slot's chemistry position is the suffix-stripped key. Formation list mirrors
docs/03-formations-lineups.md.
"""

from __future__ import annotations

FORMATIONS: dict[str, tuple[str, ...]] = {
    "4-2-3-1": ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST"),
    "4-3-3": ("GK", "RB", "CB1", "CB2", "LB", "CM1", "CM2", "CM3", "RW", "LW", "ST"),
    "4-4-2": ("GK", "RB", "CB1", "CB2", "LB", "RM", "CM1", "CM2", "LM", "ST1", "ST2"),
    "4-2-2-2": ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM1", "CAM2", "ST1", "ST2"),
    "4-1-2-1-2": ("GK", "RB", "CB1", "CB2", "LB", "CDM", "CM1", "CM2", "CAM", "ST1", "ST2"),
    "3-5-2": ("GK", "CB1", "CB2", "CB3", "RM", "CDM1", "CDM2", "CAM", "LM", "ST1", "ST2"),
    "5-2-1-2": ("GK", "RWB", "CB1", "CB2", "CB3", "LWB", "CM1", "CM2", "CAM", "ST1", "ST2"),
    "5-3-2": ("GK", "RWB", "CB1", "CB2", "CB3", "LWB", "CM1", "CM2", "CM3", "ST1", "ST2"),
    "4-5-1": ("GK", "RB", "CB1", "CB2", "LB", "RM", "CM1", "CM2", "CM3", "LM", "ST"),
    "4-3-2-1": ("GK", "RB", "CB1", "CB2", "LB", "CM1", "CM2", "CM3", "CF1", "CF2", "ST"),
    "3-4-3": ("GK", "CB1", "CB2", "CB3", "RM", "CM1", "CM2", "LM", "RW", "LW", "ST"),
    "4-1-4-1": ("GK", "RB", "CB1", "CB2", "LB", "CDM", "RM", "CM1", "CM2", "LM", "ST"),
}


def slot_position(slot_key: str) -> str:
    """'CB1' -> 'CB'; 'GK' -> 'GK'."""
    return slot_key.rstrip("0123456789")
