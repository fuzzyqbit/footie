"""Shared HTTP fetch for ingest crawlers."""

from __future__ import annotations

import httpx

from ..errors import FetchError

USER_AGENT = "footie-playbook/0.1 (personal squad tool)"
TIMEOUT_SECONDS = 15


def fetch_html(url: str) -> str:
    """GET a page (1 retry), or raise FetchError."""
    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = httpx.get(
                url, timeout=TIMEOUT_SECONDS, follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
    raise FetchError(f"could not fetch {url}: {last_error}")
