"""Employment Situation and CPI, from the Bureau's own RSS feeds."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

import httpx

from datafeed.http import HEADERS
from datafeed.rss import DEFAULT_LIMIT, cap_limit, fetch_xml, parse_release_rss

SOURCE = "bls"
EMPLOYMENT_URL = "https://www.bls.gov/feed/empsit.rss"
CPI_URL = "https://www.bls.gov/feed/cpi.rss"
_SERIES = {"employment": EMPLOYMENT_URL, "cpi": CPI_URL}
_SERIES_ERROR = "Series must be employment, cpi, or both."


def series_names(value: str) -> list[str] | None:
    """``employment``, ``cpi``, or both when the text is blank. ``None`` when unknown."""
    text = (value or "").strip().casefold()
    if not text:
        return ["employment", "cpi"]
    chosen: list[str] = []
    for part in text.split(","):
        name = part.strip()
        if not name:
            continue
        if name not in _SERIES:
            return None
        if name not in chosen:
            chosen.append(name)
    return chosen or None


class BlsReleases:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def releases(self, series: str = "", *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Employment Situation, CPI, or both. Each item names its series."""
        chosen = series_names(series)
        if chosen is None:
            return {"query": " ".join((series or "").split()), "count": 0, "items": [], "error": _SERIES_ERROR}
        label = ",".join(chosen)
        items: list[dict[str, str]] = []
        errors: list[str] = []
        for name in chosen:
            try:
                xml_text = fetch_xml(self._client, _SERIES[name], {}, headers=HEADERS)
            except httpx.HTTPError as exc:
                errors.append(f"{name}: {_detail(exc)}")
                continue
            try:
                items.extend(parse_release_rss(xml_text, limit=limit, source=SOURCE, series=name))
            except ElementTree.ParseError:
                errors.append(f"{name}: not readable")
        if items:
            kept = _mix(items, chosen, cap_limit(limit))
            return {"query": label, "count": len(kept), "items": kept}
        if errors:
            return {"query": label, "count": 0, "items": [], "error": f"Release feed failed: {'; '.join(errors)}"}
        return {"query": label, "count": 0, "items": []}


def _mix(items: list[dict[str, str]], chosen: list[str], limit: int) -> list[dict[str, str]]:
    """Round-robin so a short limit still includes each series that returned."""
    buckets = [[item for item in items if item.get("series") == name] for name in chosen]
    mixed: list[dict[str, str]] = []
    while len(mixed) < limit and any(buckets):
        for bucket in buckets:
            if len(mixed) >= limit:
                break
            if bucket:
                mixed.append(bucket.pop(0))
    return mixed


def _detail(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return "network error"
