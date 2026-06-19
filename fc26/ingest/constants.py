"""Lightweight ingest constants — no heavy imports.

These defaults are needed at CLI option-decoration time. Keeping them here (not
in refresh.py, which transitively pulls selectolax + httpx) lets cli.py import
them cheaply without dragging the scrape graph into `fc26 --help`.
"""

from __future__ import annotations

DEFAULT_MIN_OVR = 84
DEFAULT_INTERVAL_HOURS = 72.0   # every 3 days — gentle on the source sites
