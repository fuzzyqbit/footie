from fc26.merge import merge_cards
from fc26.models import Card, FaceStats


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


FUTGG = "https://www.fut.gg/players/231866-rodri/26-1/"
FCRATINGS = "https://www.fcratings.com/lists/top-100-players"


def test_incoming_wins_when_neither_is_futgg():
    existing = _card(ovr=89, source_url=FCRATINGS)
    incoming = _card(ovr=90, source_url=FCRATINGS)
    assert merge_cards(existing, incoming).ovr == 90


def test_incoming_nulls_filled_from_existing():
    existing = _card(club="Manchester City F.C.", face=FaceStats(pac=72))
    incoming = _card(ovr=90, club=None, face=FaceStats(sho=78))
    merged = merge_cards(existing, incoming)
    assert merged.ovr == 90
    assert merged.club == "Manchester City F.C."
    assert merged.face.pac == 72  # kept from existing
    assert merged.face.sho == 78  # taken from incoming


def test_futgg_existing_beats_fcratings_incoming():
    existing = _card(
        ovr=89,
        league="Premier League",
        nation="Spain",
        playstyles_plus=("Intercept",),
        source_url=FUTGG,
    )
    incoming = _card(ovr=88, league=None, source_url=FCRATINGS)
    merged = merge_cards(existing, incoming)
    assert merged.ovr == 89  # rich fut.gg value kept
    assert merged.league == "Premier League"
    assert merged.playstyles_plus == ("Intercept",)
    assert merged.source_url == FUTGG


def test_futgg_incoming_beats_futgg_existing():
    existing = _card(ovr=89, source_url=FUTGG)
    incoming = _card(ovr=90, source_url=FUTGG)
    assert merge_cards(existing, incoming).ovr == 90


def test_empty_tuple_treated_as_missing():
    existing = _card(playstyles_plus=("Intercept",))
    incoming = _card(playstyles_plus=())
    assert merge_cards(existing, incoming).playstyles_plus == ("Intercept",)


def test_empty_string_treated_as_missing():
    existing = _card(club="Arsenal F.C.")
    incoming = _card(club="")
    assert merge_cards(existing, incoming).club == "Arsenal F.C."


def test_zero_integer_treated_as_present():
    existing = _card(price=500)
    incoming = _card(price=0)
    assert merge_cards(existing, incoming).price == 0  # 0 is present, not missing


def test_subs_merge_is_atomic_by_design():
    # Spec: subs only ever arrives complete from fut.gg crawls, so it is
    # replaced as a whole object, never merged field-wise.
    from fc26.models import SubStats

    existing = _card(subs=SubStats(acceleration=80))
    incoming = _card(subs=SubStats(sprint_speed=90))
    assert merge_cards(existing, incoming).subs == SubStats(sprint_speed=90)
