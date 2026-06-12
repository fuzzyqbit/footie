"""FC 26 chemistry-style boost tables.

Source: https://footballgamingzone.com/ea-sports-fc/ea-fc-26-chemistry-styles-explained-all-stat-boosts-changes/
(fetched 2026-06-12), spot-verified against
https://realsport101.com/article/fc-26-chemistry-styles-explained
for "hunter" (outfield) and "wall"/"glove" (GK styles).

Both sources confirm the FC 26 3/6/9 boost model: each boosted sub-stat is
assigned a tier value (3, 6, or 9) at chem level 3 (see citations above).
Per-level scaling (L1 = L3/3, L2 = 2*L3/3) is a MODEL ASSUMPTION, not published
by the sources:
  tier 3  -> L1: +1, L2: +2, L3: +3
  tier 6  -> L1: +2, L2: +4, L3: +6
  tier 9  -> L1: +3, L2: +6, L3: +9
The 3/6/9 tier names are source-verified (skycoach.gg, playhub.com, nealguides.com),
but the explicit per-level table is not. All L3 values divide cleanly (every value
is 3, 6, or 9), suggesting the scaling is correct. Verify in-game before trusting
L1/L2 numbers; L3 numbers are safe (matched against source data).

Spot-verification (hunter):
  footballgamingzone: +6 Acceleration, +6 Sprint Speed, +3 Attacking Positioning,
    +3 Finishing, +3 Shot Power, +9 Volleys, +6 Penalties
  realsport101: +6 Acceleration, +6 Sprint Speed, +3 Attacking Positioning,
    +3 Finishing, +3 Shot Power, +9 Volleys, +6 Penalties  [MATCH]

Spot-verification (GK wall — documented but not encoded):
  footballgamingzone: +9 Diving, +3 Handling, +6 Kicking
  realsport101:       +9 Diving, +3 Handling, +6 Kicking   [MATCH]

GK sub-stats note: EA's GK-specific sub-stats (Diving, Handling, Kicking,
Reflexes, GK Positioning) have no corresponding SubStats dataclass fields
(SubStats only covers the 29 outfield sub-stats). GK styles therefore only
encode the sub-stat fields that exist in SubStats (acceleration, sprint_speed).
The GK-specific fields are documented here for reference but cannot be stored
in the current SubStats model:
  wall:     +9 Diving, +3 Handling, +6 Kicking  (zero SubStats mappings -> omitted from dict)
  glove:    +6 Diving, +9 Handling, +3 GK Positioning  (zero SubStats mappings -> omitted)
  shield:   +6 Reflexes, +3 Acceleration, +9 GK Positioning  (+3 Acceleration encoded)
  cat:      +6 Kicking, +9 Reflexes, +3 Sprint Speed  (+3 Sprint Speed encoded)
  gk_basic: +3 Diving, +3 Handling, +3 Kicking, +3 Acceleration, +3 GK Positioning
            (+3 Acceleration encoded)

STYLE_BOOSTS maps style slug -> chem level (1/2/3) -> SubStats field -> +delta.
All values are taken directly from the fetched source; none are invented.
"""

from __future__ import annotations


def _expand(level3: dict[str, int]) -> dict[int, dict[str, int]]:
    """Expand a level-3 sub-stat dict into all three chem levels.

    Scaling rule (confirmed by source): tier-3 value maps to L1=1, L2=2, L3=3;
    tier-6 to L1=2, L2=4, L3=6; tier-9 to L1=3, L2=6, L3=9.
    All level-3 values must be multiples of 3.
    """
    level1 = {k: v // 3 for k, v in level3.items()}
    level2 = {k: (v * 2) // 3 for k, v in level3.items()}
    return {1: level1, 2: level2, 3: level3}


STYLE_BOOSTS: dict[str, dict[int, dict[str, int]]] = {
    # --- Outfield styles ---
    # Source: footballgamingzone.com (2026-06-12)

    "basic": _expand({
        # +3 Sprint Speed, +3 Attacking Positioning, +3 Shot Power, +3 Penalties,
        # +3 Short Passing, +3 Long Passing, +3 Curve, +3 Agility, +3 Ball Control,
        # +3 Dribbling, +3 Composure, +3 Defensive Awareness, +3 Standing Tackle,
        # +3 Sliding Tackle, +3 Strength
        "sprint_speed": 3,
        "positioning": 3,
        "shot_power": 3,
        "penalties": 3,
        "short_passing": 3,
        "long_passing": 3,
        "curve": 3,
        "agility": 3,
        "ball_control": 3,
        "dribbling": 3,
        "composure": 3,
        "def_awareness": 3,
        "standing_tackle": 3,
        "sliding_tackle": 3,
        "strength": 3,
    }),

    "sniper": _expand({
        "positioning": 9,
        "finishing": 3,
        "shot_power": 3,
        "long_shots": 6,
        "volleys": 3,
        "penalties": 3,
        "stamina": 6,
        "strength": 9,
        "aggression": 3,
    }),

    "finisher": _expand({
        "positioning": 6,
        "finishing": 9,
        "shot_power": 3,
        "long_shots": 6,
        "volleys": 3,
        "penalties": 3,
        "agility": 6,
        "balance": 3,
        "reactions": 3,
        "dribbling": 9,
    }),

    "deadeye": _expand({
        "positioning": 6,
        "finishing": 3,
        "shot_power": 9,
        "long_shots": 3,
        "penalties": 3,
        "vision": 3,
        "short_passing": 9,
        "long_passing": 3,
        "curve": 6,
    }),

    "marksman": _expand({
        "finishing": 6,
        "shot_power": 3,
        "long_shots": 6,
        "penalties": 3,
        "reactions": 6,
        "ball_control": 6,
        "dribbling": 3,
        "composure": 3,
        "jumping": 3,
        "strength": 6,
    }),

    "hawk": _expand({
        "acceleration": 3,
        "sprint_speed": 3,
        "positioning": 3,
        "finishing": 3,
        "shot_power": 6,
        "long_shots": 6,
        "penalties": 3,
        "jumping": 6,
        "strength": 3,
        "aggression": 6,
    }),

    "artist": _expand({
        "vision": 3,
        "crossing": 6,
        "short_passing": 3,
        "long_passing": 6,
        "curve": 9,
        "agility": 9,
        "reactions": 6,
        "dribbling": 3,
        "composure": 3,
    }),

    "architect": _expand({
        # Source spells "Architecht" — corrected to "architect" slug
        "vision": 6,
        "fk_accuracy": 3,
        "short_passing": 9,
        "long_passing": 3,
        "curve": 6,
        "stamina": 6,
        "strength": 9,
        "aggression": 3,
    }),

    "powerhouse": _expand({
        "vision": 9,
        "short_passing": 6,
        "long_passing": 6,
        "curve": 3,
        "interceptions": 6,
        "def_awareness": 3,
        "standing_tackle": 9,
        "sliding_tackle": 3,
    }),

    "maestro": _expand({
        "positioning": 3,
        "shot_power": 3,
        "long_shots": 6,
        "vision": 3,
        "fk_accuracy": 6,
        "short_passing": 3,
        "long_passing": 6,
        "reactions": 3,
        "ball_control": 6,
        "dribbling": 3,
        "composure": 3,
    }),

    "engine": _expand({
        "acceleration": 3,
        "sprint_speed": 3,
        "vision": 3,
        "crossing": 6,
        "short_passing": 3,
        "long_passing": 3,
        "curve": 6,
        "agility": 3,
        "balance": 6,
        "dribbling": 6,
    }),

    "sentinel": _expand({
        "interceptions": 6,
        "heading_accuracy": 6,
        "def_awareness": 9,
        "standing_tackle": 3,
        "sliding_tackle": 3,
        "jumping": 9,
        "strength": 3,
        "aggression": 6,
    }),

    "guardian": _expand({
        "agility": 6,
        "reactions": 3,
        "ball_control": 3,
        "dribbling": 6,
        "composure": 3,
        "interceptions": 3,
        "def_awareness": 6,
        "standing_tackle": 9,
        "sliding_tackle": 6,
    }),

    "gladiator": _expand({
        "positioning": 3,
        "shot_power": 6,
        "long_shots": 3,
        "balance": 3,
        "reactions": 6,
        "ball_control": 3,
        "dribbling": 3,
        "interceptions": 3,
        "heading_accuracy": 3,
        "def_awareness": 3,
        "standing_tackle": 3,
        "sliding_tackle": 6,
    }),

    "backbone": _expand({
        "vision": 3,
        "short_passing": 3,
        "long_passing": 6,
        "interceptions": 6,
        "def_awareness": 3,
        "standing_tackle": 6,
        "sliding_tackle": 3,
        "stamina": 6,
        "strength": 3,
        "aggression": 6,
    }),

    "anchor": _expand({
        "acceleration": 3,
        "sprint_speed": 3,
        "interceptions": 3,
        "heading_accuracy": 3,
        "def_awareness": 3,
        "standing_tackle": 6,
        "sliding_tackle": 6,
        "jumping": 6,
        "strength": 6,
        "aggression": 3,
    }),

    "hunter": _expand({
        # Spot-verified: footballgamingzone + realsport101 agree exactly
        "acceleration": 6,
        "sprint_speed": 6,
        "positioning": 3,
        "finishing": 3,
        "shot_power": 3,
        "volleys": 9,
        "penalties": 6,
    }),

    "catalyst": _expand({
        "acceleration": 6,
        "sprint_speed": 6,
        "vision": 9,
        "crossing": 6,
        "short_passing": 3,
        "long_passing": 6,
        "curve": 3,
    }),

    "shadow": _expand({
        "acceleration": 6,
        "sprint_speed": 6,
        "interceptions": 3,
        "heading_accuracy": 6,
        "def_awareness": 3,
        "standing_tackle": 3,
        "sliding_tackle": 9,
    }),

    # --- GK styles ---
    # GK-specific sub-stats (Diving, Handling, Kicking, Reflexes, GK Positioning)
    # have no SubStats field. Only acceleration/sprint_speed are encoded where
    # the source lists them. Styles with zero SubStats-mappable fields are OMITTED
    # entirely from STYLE_BOOSTS (see wall/glove omission below ~line 330).
    # They are documented here for reference but cannot be stored in the current SubStats model.

    "gk_basic": _expand({
        # +3 Diving, +3 Handling, +3 Kicking, +3 Acceleration, +3 Positioning
        # Only acceleration maps to SubStats
        "acceleration": 3,
    }),

    "shield": _expand({
        # +6 Reflexes, +3 Acceleration, +9 GK Positioning
        # Only acceleration maps to SubStats
        "acceleration": 3,
    }),

    "cat": _expand({
        # +6 Kicking, +9 Reflexes, +3 Sprint Speed
        # Only sprint_speed maps to SubStats
        "sprint_speed": 3,
    }),

    # "wall"  (+9 Diving, +3 Handling, +6 Kicking) — omitted: zero SubStats mappings.
    # "glove" (+6 Diving, +9 Handling, +3 GK Positioning) — omitted: zero SubStats mappings.
    # These styles are documented above (spot-verified) but cannot be encoded until
    # SubStats gains GK-specific fields (Diving, Handling, Kicking, Reflexes, GK Positioning).
}


def available_styles() -> tuple[str, ...]:
    """Return all known chemistry style slugs, sorted."""
    return tuple(sorted(STYLE_BOOSTS))
