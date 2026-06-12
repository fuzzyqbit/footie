import pytest

from fc26.chem.styles import STYLE_BOOSTS, available_styles
from fc26.models import SubStats

SUB_FIELDS = set(SubStats.__dataclass_fields__)


def test_structure_all_styles_valid():
    assert len(STYLE_BOOSTS) >= 20
    for style, levels in STYLE_BOOSTS.items():
        assert style == style.lower(), style          # slug keys
        for level, boosts in levels.items():
            assert level in (1, 2, 3), (style, level)
            assert boosts, (style, level)
            for sub, delta in boosts.items():
                assert sub in SUB_FIELDS, (style, sub)
                assert isinstance(delta, int) and delta > 0, (style, sub, delta)


def test_available_styles_sorted():
    styles = available_styles()
    assert styles == tuple(sorted(styles))
    assert "hunter" in styles


def test_pinned_hunter_level3():
    # Pinned to footballgamingzone.com values (2026-06-12),
    # spot-verified against realsport101.com — both sources agree exactly.
    boosts = STYLE_BOOSTS["hunter"][3]
    assert boosts["acceleration"] == 6
    assert boosts["sprint_speed"] == 6
    assert boosts["positioning"] == 3
    assert boosts["finishing"] == 3
    assert boosts["shot_power"] == 3
    assert boosts["volleys"] == 9
    assert boosts["penalties"] == 6


def test_level_scaling_model_assumption():
    # Pins the documented MODEL ASSUMPTION (L3/3, 2*L3/3), not source data.
    # Sources confirm the 3/6/9 tier model, but none publish explicit per-level tables.
    # Scaling rule: L1 = L3 // 3, L2 = (L3 * 2) // 3
    assert STYLE_BOOSTS["hunter"][1]["acceleration"] == 2   # 6 // 3
    assert STYLE_BOOSTS["hunter"][2]["acceleration"] == 4   # (6*2) // 3
    assert STYLE_BOOSTS["hunter"][1]["volleys"] == 3        # 9 // 3
    assert STYLE_BOOSTS["hunter"][2]["volleys"] == 6        # (9*2) // 3


def test_pinned_gk_style():
    # GK cat: +6 Kicking, +9 Reflexes, +3 Sprint Speed (source: footballgamingzone.com)
    # Only sprint_speed maps to SubStats; verified against realsport101.com.
    assert "cat" in STYLE_BOOSTS
    boosts = STYLE_BOOSTS["cat"][3]
    assert boosts["sprint_speed"] == 3

    # GK shield: +6 Reflexes, +3 Acceleration, +9 GK Positioning
    # Only acceleration maps to SubStats.
    assert "shield" in STYLE_BOOSTS
    assert STYLE_BOOSTS["shield"][3]["acceleration"] == 3

    # GK gk_basic: +3 Acceleration among others
    assert "gk_basic" in STYLE_BOOSTS
    assert STYLE_BOOSTS["gk_basic"][3]["acceleration"] == 3


def test_pinned_shadow_level3():
    # Pinned from footballgamingzone.com (2026-06-12)
    boosts = STYLE_BOOSTS["shadow"][3]
    assert boosts["acceleration"] == 6
    assert boosts["sprint_speed"] == 6
    assert boosts["interceptions"] == 3
    assert boosts["heading_accuracy"] == 6
    assert boosts["def_awareness"] == 3
    assert boosts["standing_tackle"] == 3
    assert boosts["sliding_tackle"] == 9


def test_all_level3_values_are_multiples_of_3():
    """All level-3 values must be 3, 6, or 9 (the FC26 boost tiers)."""
    for style, levels in STYLE_BOOSTS.items():
        for sub, delta in levels[3].items():
            assert delta in (3, 6, 9), f"{style}.{sub} level-3 value {delta} not in (3,6,9)"


def test_scaling_consistency():
    """Level 1 = L3//3, level 2 = (L3*2)//3 for all styles and sub-stats."""
    for style, levels in STYLE_BOOSTS.items():
        for sub, l3_val in levels[3].items():
            assert levels[1][sub] == l3_val // 3, f"{style}.{sub} L1 wrong"
            assert levels[2][sub] == (l3_val * 2) // 3, f"{style}.{sub} L2 wrong"
