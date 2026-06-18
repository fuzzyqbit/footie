import contextlib

from fc26.ingest import refresh as refresh_mod
from fc26.ingest.enrich import EnrichResult
from fc26.ingest.expand import ExpandResult
from fc26.ingest.refresh import RefreshResult, refresh_data


class _StubRepo:
    """Minimal repo stub: refresh_data wraps the scrape in repo.batch()."""

    @contextlib.contextmanager
    def batch(self):
        yield self


def test_refresh_runs_expand_then_enrich_and_aggregates(monkeypatch):
    calls = []

    def fake_expand(repo, *, min_ovr, fetch_html, sleep, on_progress=lambda _m: None, **kw):
        calls.append(("expand", min_ovr))
        return ExpandResult(seen=10, new=3, merged=7, failed_pages=(),
                            new_ids=("a--base", "b--base", "c--base"))

    def fake_enrich(repo, *, fetch_html, sleep, on_progress=lambda _m: None, limit=None, **kw):
        calls.append(("enrich", limit))
        return EnrichResult(enriched=("a", "b"), skipped=(), missed=())

    monkeypatch.setattr(refresh_mod, "expand_cards", fake_expand)
    monkeypatch.setattr(refresh_mod, "enrich_cards", fake_enrich)

    result = refresh_data(
        repo=_StubRepo(), min_ovr=90, fetch_html=lambda _u: "", sleep=lambda _s: None,
        enrich_limit=5,
    )

    assert isinstance(result, RefreshResult)
    assert [c[0] for c in calls] == ["expand", "enrich"]   # order matters
    assert calls[0] == ("expand", 90)
    assert calls[1] == ("enrich", 5)
    assert result.expand.new == 3
    assert len(result.enrich.enriched) == 2


def test_create_app_default_has_no_auto_refresh(tmp_path):
    # auto_refresh defaults off so importing/constructing the app never starts
    # a scrape loop in tests or one-off API use.
    from fc26.api.app import create_app

    app = create_app(db_path=tmp_path / "db.json", squads_dir=tmp_path)
    assert app.title == "FC 26 API"
