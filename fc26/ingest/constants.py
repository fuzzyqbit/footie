"""Lightweight ingest constants — no heavy imports.

These defaults are needed at CLI option-decoration time. Keeping them here (not
in refresh.py, which transitively pulls selectolax + httpx) lets cli.py import
them cheaply without dragging the scrape graph into `fc26 --help`.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from ..errors import RateLimitedError

DEFAULT_MIN_OVR = 84
DEFAULT_INTERVAL_HOURS = 72.0   # every 3 days — gentle on the source sites

# Statuses that mean "the host is refusing this client" (Cloudflare block / rate
# limit). Retrying or moving on to the next URL only deepens the block.
BLOCKED_STATUSES = (403, 429)


def rate_limited_error(url: str, status: int, retry_after_header: str | None) -> RateLimitedError:
    """Build the RateLimitedError for a blocked response (shared with web.py)."""
    retry_after = int(retry_after_header) if (retry_after_header or "").isdigit() else None
    host = urlsplit(url).netloc
    wait = f"retry after ~{max(retry_after // 60, 1)} min" if retry_after else "wait before retrying"
    return RateLimitedError(f"{host} blocked us (HTTP {status}) - {wait}: {url}", retry_after)
