import httpx
import pytest

import fc26.ingest.web as web
from fc26.errors import FetchError


def _client_with(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_fetch_html_returns_body(monkeypatch):
    def handler(request):
        assert request.headers["user-agent"] == web.USER_AGENT
        return httpx.Response(200, text="<html>ok</html>")

    monkeypatch.setattr(web.httpx, "get",
                        lambda url, **kw: _client_with(handler).get(url, headers=kw.get("headers")))
    assert web.fetch_html("https://example.test/page") == "<html>ok</html>"


def test_fetch_html_retries_then_raises_fetch_error(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(503)

    monkeypatch.setattr(web.httpx, "get",
                        lambda url, **kw: _client_with(handler).get(url, headers=kw.get("headers")))
    with pytest.raises(FetchError, match="could not fetch"):
        web.fetch_html("https://example.test/page")
    assert len(calls) == 2  # one retry
