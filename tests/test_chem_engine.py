from fc26.chem.engine import ChemReport, compute_chemistry
from fc26.chem.lineup import Lineup, Manager
from fc26.models import Card

# 4-2-3-1 slots in order
SLOTS = ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")
POSITIONS = {"GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
             "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST"}


def _xi(card_for_slot):
    """Build (lineup, slot_cards) from a slot->Card factory."""
    cards = {slot: card_for_slot(slot) for slot in SLOTS}
    lineup = Lineup(name="T", formation="4-2-3-1",
                    slots=tuple((slot, cards[slot].id) for slot in SLOTS))
    return lineup, cards


def _player(slot, *, club=None, nation=None, league=None, version="base",
            position=None, alt=()):
    return Card(
        id=f"{slot.lower()}--{version.lower().replace(' ', '-')}",
        player_name=slot, version=version, ovr=88,
        position=position or POSITIONS[slot], alt_positions=alt,
        club=club or f"Club {slot}", nation=nation, league=league,
    )


def test_full_league_core_squad():
    # All 11: same league (11 >= 8 -> league tier 3 = 3 pts) - via an alias pair.
    # Nations: GK+RB share "Spain" (2 >= 2 -> +1); other 9 unique nations (0).
    # Clubs: CB1+CB2 share Arsenal via alias pair (2 -> +1); others unique (0).
    # GK: 3(league) + 1(nation) = 4 -> cap 3.  CB1: 3 + 1(club) = 4 -> cap 3.
    # CAM: 3 + 0 + 0 = 3. Everyone = 3; team total 33.
    nations = {"GK": "Spain", "RB": "Spain"}
    clubs = {"CB1": "Arsenal", "CB2": "Arsenal F.C."}  # alias pair must unify

    def make(slot):
        return _player(slot, club=clubs.get(slot),
                       nation=nations.get(slot, f"Nation {slot}"),
                       league="Premier League" if slot != "ST" else "English Premier League")

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    assert report.team_total == 33
    assert all(p.chem == 3 for p in report.players)
    league_tier = next(t for t in report.tiers if t.kind == "league")
    assert league_tier.count == 11
    assert league_tier.points == 3
    assert league_tier.next_tier_at is None


def test_threshold_tiers_and_near_miss():
    # 4 PL players (>=3 -> tier 1, next at 5), 7 others in unique leagues.
    # All unique nations/clubs -> nation/club contribute 0.
    # PL players: 1 chem each; others: 0.
    def make(slot):
        league = "Premier League" if slot in ("GK", "RB", "CB1", "CB2") else f"L {slot}"
        return _player(slot, nation=f"N {slot}", league=league)

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    pl = next(t for t in report.tiers if t.kind == "league" and t.count == 4)
    assert pl.points == 1
    assert pl.next_tier_at == 5            # near-miss hint: +1 player -> tier 2
    gk = next(p for p in report.players if p.slot == "GK")
    st = next(p for p in report.players if p.slot == "ST")
    assert gk.chem == 1
    assert st.chem == 0


def test_out_of_position_zero_chem_and_zero_contribution():
    # ST slot filled by a CAM-only player: out of position.
    # GK+ST share nation "Spain": with ST out of position the nation count is 1
    # -> below tier -> GK gets 0 nation points.
    def make(slot):
        if slot == "ST":
            return _player(slot, position="CAM", nation="Spain", league=f"L {slot}")
        return _player(slot, nation="Spain" if slot == "GK" else f"N {slot}",
                       league=f"L {slot}")

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    st = next(p for p in report.players if p.slot == "ST")
    gk = next(p for p in report.players if p.slot == "GK")
    assert st.in_position is False
    assert st.chem == 0
    assert gk.chem == 0                    # nation count stayed at 1


def test_alt_position_counts_as_in_position():
    def make(slot):
        if slot == "ST":
            return _player(slot, position="CAM", alt=("ST",), nation=f"N {slot}", league=f"L {slot}")
        return _player(slot, nation=f"N {slot}", league=f"L {slot}")

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    st = next(p for p in report.players if p.slot == "ST")
    assert st.in_position is True


def test_icon_flat_three_and_weights():
    # CAM = Icon (nation "Brazil"). RB+CB1 also "Brazil".
    # Nation count for Brazil = 2 (icon) + 1 + 1 = 4 -> still tier 1 (2..4) -> +1 each.
    # Icon adds +1 to EVERY league: the 4 PL players (GK,RB,CB1,CB2) count 4+1=5 -> tier 2 = 2 pts.
    # GK: league 2 + nation 0 + club 0 = 2. RB: league 2 + nation 1 = 3.
    # Icon CAM itself: flat 3.
    def make(slot):
        if slot == "CAM":
            return _player(slot, version="Thunderstruck Icon", nation="Brazil",
                           league="Icons", club="EA FC ICONS")
        league = "Premier League" if slot in ("GK", "RB", "CB1", "CB2") else f"L {slot}"
        nation = "Brazil" if slot in ("RB", "CB1") else f"N {slot}"
        return _player(slot, nation=nation, league=league)

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    cam = next(p for p in report.players if p.slot == "CAM")
    gk = next(p for p in report.players if p.slot == "GK")
    rb = next(p for p in report.players if p.slot == "RB")
    assert cam.chem == 3
    assert gk.chem == 2
    assert rb.chem == 3
    brazil = next(t for t in report.tiers if t.kind == "nation" and t.count == 4)
    assert brazil.points == 1


def test_hero_double_league_weight():
    # CAM = Hero in "Premier League". GK+RB also PL.
    # League count = 2(hero) + 1 + 1 = 4 -> tier 1 (3..4) -> +1.
    # Hero itself: flat 3.
    def make(slot):
        if slot == "CAM":
            return _player(slot, version="Base Heroes", nation="N CAM", league="Premier League")
        league = "Premier League" if slot in ("GK", "RB") else f"L {slot}"
        return _player(slot, nation=f"N {slot}", league=league)

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    cam = next(p for p in report.players if p.slot == "CAM")
    gk = next(p for p in report.players if p.slot == "GK")
    assert cam.chem == 3
    assert gk.chem == 1


def test_manager_bonus_single_plus_one():
    # Manager league PL + nation Spain. GK is PL AND Spanish -> still only +1.
    # GK otherwise 0 (unique club, nation count 1, league count 1 < 3).
    def make(slot):
        if slot == "GK":
            return _player(slot, nation="Spain", league="Premier League")
        return _player(slot, nation=f"N {slot}", league=f"L {slot}")

    lineup, cards = _xi(make)
    lineup = Lineup(name=lineup.name, formation=lineup.formation, slots=lineup.slots,
                    manager=Manager(league="English Premier League", nation="Spain"))
    report = compute_chemistry(lineup, cards)
    gk = next(p for p in report.players if p.slot == "GK")
    assert gk.chem == 1   # exactly one manager point, alias-matched league


def test_unknown_league_flagged_not_silent():
    def make(slot):
        league = None if slot == "ST" else f"L {slot}"
        return _player(slot, nation=f"N {slot}", league=league)

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    assert any("st--base" in w and "league unknown" in w for w in report.warnings)


def test_pseudo_league_contributes_nothing():
    # Three "Men's National" cards: league must NOT tier (pseudo), nations still count.
    def make(slot):
        if slot in ("GK", "RB", "CB1"):
            return _player(slot, nation="Italy", league="Men's National")
        return _player(slot, nation=f"N {slot}", league=f"L {slot}")

    lineup, cards = _xi(make)
    report = compute_chemistry(lineup, cards)
    assert not any(t.kind == "league" and "national" in t.name.lower() for t in report.tiers)
    gk = next(p for p in report.players if p.slot == "GK")
    assert gk.chem == 1   # Italy nation count 3 -> tier 1 (2..4) -> +1; no league pts
