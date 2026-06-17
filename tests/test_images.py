import pytest

from fc26.db import CardRepository
from fc26.errors import ParseError
from fc26.ingest.images import (
    ImagesResult,
    parse_player_art,
    parse_player_images,
    parse_player_playstyles,
    upgrade_card_images,
)
from fc26.models import Card, FaceStats

FACE = FaceStats(pac=90, sho=90, pas=90, dri=90, def_=60, phy=80)

CDN = "https://cdn3.futbin.com/content/fifa26/img"
HD_PLAYER = f"{CDN}/players/p100894739.png?fm=png&w=485&s=aaa"
HD_BG = f"{CDN}/cards/hd/5_toty.png?fm=png&w=644&s=bbb"

# Detail page carries the main card at the largest width plus several smaller
# related-card thumbnails; the parser must pick the largest-w of each layer.
DETAIL_HTML = f"""
<html><body>
  <img class="lazy" src="{CDN}/players/p100894739.png?fm=png&amp;w=64&amp;s=zzz">
  <img src="{CDN}/cards/tiny/5_toty.png?fm=png&amp;w=10&amp;s=tiny">
  <img src="{CDN}/players/p200000000.png?fm=png&amp;w=252&amp;s=rel">
  <img src="{CDN}/cards/hd/3_gold.png?fm=png&amp;w=252&amp;s=rel">
  <img class="main" src="{HD_PLAYER.replace('&', '&amp;')}">
  <img class="main" src="{HD_BG.replace('&', '&amp;')}">
</body></html>
"""


def _card(card_id, *, futbin_url=None, image_url=None, bg_url=None) -> Card:
    return Card(id=card_id, player_name=card_id, version="TOTY", ovr=90,
                position="ST", face=FACE, futbin_url=futbin_url,
                image_url=image_url, bg_url=bg_url)


def test_parse_picks_largest_width_layers():
    image_url, bg_url = parse_player_images(DETAIL_HTML)
    assert image_url == HD_PLAYER     # w=485 beats w=64 and the w=252 related card
    assert bg_url == HD_BG            # w=644 beats w=10 and w=252


def test_parse_returns_none_when_absent():
    assert parse_player_images("<html><body>nope</body></html>") == (None, None)


# Detail pages carry crest/league/flag logos as <img alt=...> in both dark and
# light variants (dark matches the card overlay); the player render's alt is the
# short/common name even though the H1/og:title give the full legal name.
LOGO_HTML = f"""
<html><body>
  <img class="main" alt="Aitana Bonmatí" src="{CDN}/players/p100894739.png?fm=png&amp;w=485&amp;s=aaa">
  <img alt="Aitana Bonmatí Conca" src="{CDN}/players/p100894739.png?fm=png&amp;w=64&amp;s=zzz">
  <img alt="Club" src="{CDN}/clubs/light/241.png?fm=png&amp;w=22&amp;s=cl">
  <img alt="Club" src="{CDN}/clubs/dark/241.png?fm=png&amp;w=22&amp;s=cd">
  <img alt="League" src="{CDN}/league/light/2222.png?fm=png&amp;w=22&amp;s=ll">
  <img alt="League" src="{CDN}/league/dark/2222.png?fm=png&amp;w=22&amp;s=ld">
  <img alt="Nation" src="{CDN}/nation/45.png?fm=png&amp;w=22&amp;s=nn">
</body></html>
"""


def test_parse_art_extracts_logos_preferring_dark():
    art = parse_player_art(LOGO_HTML)
    assert art.club_url == f"{CDN}/clubs/dark/241.png?fm=png&w=22&s=cd"
    assert art.league_url == f"{CDN}/league/dark/2222.png?fm=png&w=22&s=ld"
    assert art.nation_url == f"{CDN}/nation/45.png?fm=png&w=22&s=nn"


def test_parse_art_common_name_from_largest_player_render():
    # The w=485 main render's alt is the short name; the w=64 thumb's full name
    # must not win.
    art = parse_player_art(LOGO_HTML)
    assert art.common_name == "Aitana Bonmatí"


def test_parse_art_missing_logos_are_none():
    art = parse_player_art("<html><body>nope</body></html>")
    assert art.club_url is None
    assert art.league_url is None
    assert art.nation_url is None
    assert art.common_name is None


def test_parse_images_still_returns_two_tuple():
    image_url, bg_url = parse_player_images(DETAIL_HTML)
    assert image_url == HD_PLAYER
    assert bg_url == HD_BG


def test_upgrade_fills_logos_and_common_name(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("a--toty", futbin_url="https://www.futbin.com/26/player/1/a"))
    result = upgrade_card_images(
        repo, fetch_html=lambda url: LOGO_HTML, sleep=lambda s: None,
    )
    assert result.upgraded == ("a--toty",)
    card = repo.find_by_id("a--toty")
    assert card.club_url == f"{CDN}/clubs/dark/241.png?fm=png&w=22&s=cd"
    assert card.league_url == f"{CDN}/league/dark/2222.png?fm=png&w=22&s=ld"
    assert card.nation_url == f"{CDN}/nation/45.png?fm=png&w=22&s=nn"
    assert card.common_name == "Aitana Bonmatí"


def test_upgrade_fills_hd_urls(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("a--toty", futbin_url="https://www.futbin.com/26/player/1/a"))
    result = upgrade_card_images(
        repo, fetch_html=lambda url: DETAIL_HTML, sleep=lambda s: None,
    )
    assert result.upgraded == ("a--toty",)
    card = repo.find_by_id("a--toty")
    assert card.image_url == HD_PLAYER
    assert card.bg_url == HD_BG


def test_upgrade_skips_cards_without_futbin_url(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("a--toty", futbin_url=None))
    result = upgrade_card_images(repo, fetch_html=lambda url: DETAIL_HTML, sleep=lambda s: None)
    assert result.upgraded == ()
    assert "a--toty" in result.skipped


def test_upgrade_skips_already_hd_unless_refresh(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("a--toty", futbin_url="https://www.futbin.com/26/player/1/a",
                      image_url=HD_PLAYER, bg_url=HD_BG))
    fetched = []

    def fetch(url):
        fetched.append(url)
        return DETAIL_HTML

    result = upgrade_card_images(repo, fetch_html=fetch, sleep=lambda s: None)
    assert result.skipped == ("a--toty",)
    assert fetched == []   # no fetch for already-HD card

    result2 = upgrade_card_images(repo, fetch_html=fetch, sleep=lambda s: None, refresh=True)
    assert result2.upgraded == ("a--toty",)
    assert len(fetched) == 1


def test_upgrade_upgrades_thumbnail_to_hd(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    thumb = f"{CDN}/players/p1.png?fm=png&w=64&s=t"
    repo.upsert(_card("a--toty", futbin_url="https://www.futbin.com/26/player/1/a",
                      image_url=thumb))
    result = upgrade_card_images(repo, fetch_html=lambda u: DETAIL_HTML, sleep=lambda s: None)
    assert result.upgraded == ("a--toty",)
    assert repo.find_by_id("a--toty").image_url == HD_PLAYER


def test_upgrade_respects_limit(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    for i in range(5):
        repo.upsert(_card(f"c{i}--toty", futbin_url=f"https://www.futbin.com/26/player/{i}/c"))
    fetched = []
    result = upgrade_card_images(
        repo, fetch_html=lambda u: (fetched.append(u) or DETAIL_HTML),
        sleep=lambda s: None, limit=2,
    )
    assert len(result.upgraded) == 2
    assert len(fetched) == 2


def test_upgrade_sleeps_once_per_fetch(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    for i in range(3):
        repo.upsert(_card(f"c{i}--toty", futbin_url=f"https://www.futbin.com/26/player/{i}/c"))
    slept = []
    upgrade_card_images(repo, fetch_html=lambda u: DETAIL_HTML, sleep=lambda s: slept.append(s))
    assert len(slept) == 3


def test_upgrade_concurrent_workers_persist_every_card(tmp_path):
    # With a thread pool the fetches overlap but the single writer must still
    # land every card — concurrent writers would clobber each other's upserts.
    repo = CardRepository(tmp_path / "players.json")
    for i in range(12):
        repo.upsert(_card(f"c{i}--toty", futbin_url=f"https://www.futbin.com/26/player/{i}/c"))
    fetched = []
    result = upgrade_card_images(
        repo, fetch_html=lambda u: (fetched.append(u) or DETAIL_HTML),
        sleep=lambda s: None, workers=4,
    )
    assert set(result.upgraded) == {f"c{i}--toty" for i in range(12)}
    assert len(fetched) == 12
    for i in range(12):
        assert repo.find_by_id(f"c{i}--toty").image_url == HD_PLAYER


def test_upgrade_aborts_when_most_fetches_fail(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    for i in range(15):
        repo.upsert(_card(f"c{i}--toty", futbin_url=f"https://www.futbin.com/26/player/{i}/c"))

    def boom(url):
        raise ParseError("fetch failed")

    with pytest.raises(ParseError, match="layout changed"):
        upgrade_card_images(repo, fetch_html=boom, sleep=lambda s: None)


# A futbin detail page lists each playstyle as an anchor; "active" => the card
# has it, "psplus" => PlayStyle+. Inactive anchors (styles the card lacks) must
# be ignored. Related cards have their own player-abilities-wrapper; only the
# first (main card) wrapper counts.
PLAYSTYLES_HTML = """
<html><body>
  <div class="player-abilities-wrapper xs-column">
    <a href="/26/playstyles/power-shot" class="playStyle-table-icon column align-center text-ellipsis active psplus">
      <img src="x.png"><div class="slim-font text-center xxs-font text-ellipsis max-width-100">Power Shot</div></a>
    <a href="/26/playstyles/first-touch" class="playStyle-table-icon column align-center text-ellipsis active">
      <img src="y.png"><div class="slim-font text-center xxs-font text-ellipsis max-width-100">First Touch</div></a>
    <a href="/26/playstyles/rapid" class="playStyle-table-icon column align-center text-ellipsis">
      <img src="z.png"><div class="slim-font text-center xxs-font text-ellipsis max-width-100">Rapid</div></a>
  </div>
  <div class="player-abilities-wrapper xs-column">
    <a href="/26/playstyles/tiki-taka" class="playStyle-table-icon column align-center active psplus">
      <img src="r.png"><div class="slim-font text-center xxs-font text-ellipsis max-width-100">Tiki Taka</div></a>
  </div>
</body></html>
"""


def test_parse_playstyles_splits_plus_and_ignores_inactive():
    playstyles, playstyles_plus = parse_player_playstyles(PLAYSTYLES_HTML)
    assert playstyles == ("First Touch",)        # active, not psplus
    assert playstyles_plus == ("Power Shot",)     # active psplus
    # "Rapid" is inactive => ignored; "Tiki Taka" is in a RELATED wrapper => ignored


def test_parse_playstyles_empty_when_none_present():
    assert parse_player_playstyles("<html><body>nope</body></html>") == ((), ())
