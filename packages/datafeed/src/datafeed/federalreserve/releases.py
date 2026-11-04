"""Federal Reserve monetary-policy press releases.

The feed is the Board's own RSS, including the FOMC statement.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

import httpx

from datafeed.rss import DEFAULT_LIMIT, fetch_xml, parse_release_rss

URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"
SOURCE = "federalreserve"
SERIES = "monetary-policy"


class FederalReserveReleases:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def releases(self, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Newest monetary-policy releases, including FOMC statements."""
        try:
            xml_text = fetch_xml(self._client, URL, {})
        except httpx.HTTPError as exc:
            return _failed(SERIES, exc)
        try:
            items = parse_release_rss(xml_text, limit=limit, source=SOURCE, series=SERIES)
        except ElementTree.ParseError:
            return _unreadable(SERIES)
        return {"query": SERIES, "count": len(items), "items": items}


def _failed(query: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError):
        detail = f"HTTP {exc.response.status_code}"
    else:
        detail = "network error"
    return {"query": query, "count": 0, "items": [], "error": f"Release feed failed: {detail}"}


def _unreadable(query: str) -> dict[str, Any]:
    return {"query": query, "count": 0, "items": [], "error": "Release feed was not readable."}
