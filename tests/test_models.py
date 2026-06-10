import dataclasses

import pytest

from fc26.models import (
    Card,
    FaceStats,
    ValidationError,
    make_card_id,
    slugify,
    validate_card,
)


def _card(**overrides) -> Card:
    base = dict(
        id="rodri--base",
        player_name="Rodri",
        version="base",
        ovr=89,
        position="CDM",
    )
    base.update(overrides)
    return Card(**base)


def test_card_is_immutable():
    card = _card()
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.ovr = 90


def test_slugify_strips_accents_and_punctuation():
    assert slugify("Kylian Mbappé") == "kylian-mbappe"
    assert slugify("Festival of Football: Path to Glory") == "festival-of-football-path-to-glory"


def test_make_card_id_is_deterministic():
    assert make_card_id("Rodri", "base") == "rodri--base"
    assert make_card_id("Cristiano Ronaldo", "TOTS") == "cristiano-ronaldo--tots"


def test_validate_accepts_valid_card():
    card = _card(face=FaceStats(pac=90, sho=88, pas=96, dri=95, def_=94, phy=92))
    assert validate_card(card) is card


def test_validate_rejects_out_of_range_ovr():
    with pytest.raises(ValidationError, match="ovr 120 out of range"):
        validate_card(_card(ovr=120))


def test_validate_rejects_unknown_position():
    with pytest.raises(ValidationError, match="unknown position 'QB'"):
        validate_card(_card(position="QB"))


def test_validate_rejects_bad_face_stat():
    with pytest.raises(ValidationError, match="face.pac 150 out of range"):
        validate_card(_card(face=FaceStats(pac=150)))


def test_validate_reports_all_failures_at_once():
    with pytest.raises(ValidationError) as exc:
        validate_card(_card(ovr=0, position="QB", skill_moves=9))
    message = str(exc.value)
    assert "ovr" in message
    assert "position" in message
    assert "skill_moves" in message


def test_face_stats_default_to_none():
    card = _card()
    assert card.face.pac is None
    assert card.subs is None


def test_validate_rejects_empty_id():
    with pytest.raises(ValidationError, match="id is empty"):
        validate_card(_card(id=""))


def test_validate_accepts_boundary_values():
    assert validate_card(_card(ovr=1)) is not None
    assert validate_card(_card(ovr=99)) is not None
    assert validate_card(_card(skill_moves=1, weak_foot=5)) is not None


def test_validate_rejects_invalid_alt_position():
    with pytest.raises(ValidationError, match="unknown alt position"):
        validate_card(_card(alt_positions=("QB",)))


def test_validate_rejects_bad_subs_stat():
    from fc26.models import SubStats

    with pytest.raises(ValidationError, match="subs.acceleration"):
        validate_card(_card(subs=SubStats(acceleration=0)))
