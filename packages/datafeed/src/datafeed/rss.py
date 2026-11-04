"""Shared RSS helpers. Each feed module owns its URL, query, and field mapping."""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx

HEADERS = {"User-Agent": "invest-research/0.1"}
DEFAULT_LIMIT = 25
MAX_LIMIT = 40
_TICKER_TOKEN = re.compile(r"(?:[A-Z]{1,6}:)?([A-Z][A-Z0-9.\-]{0,4})$")
_TAG = re.compile(r"<[^>]+>")
_WITHIN = re.compile(
    r"^(\d+)?(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$",
    re.IGNORECASE,
)
_WITHIN_ERROR = "Within must look like 30s, 5m, 1h, or 2d."
_SECONDS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


def clean_query(query: str) -> str:
    return " ".join((query or "").split())[:180]


def cap_limit(limit: int) -> int:
    try:
        cap = int(limit or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        cap = DEFAULT_LIMIT
    return max(1, min(cap, MAX_LIMIT))


def story_summary(raw: str, *, title: str = "") -> str:
    """Plain text of the feed's story. Drops a summary that is only the title or a URL."""
    text = html.unescape(_TAG.sub(" ", raw or ""))
    text = " ".join(text.split())
    if not text:
        return ""
    if text.casefold() == " ".join(title.casefold().split()):
        return ""
    if text.startswith(("http://", "https://")) and " " not in text:
        return ""
    return text[:1500]


def ticker_from_query(query: str) -> str | None:
    """First token when it looks like a ticker, for example ``AAPL`` or ``NASDAQ:AAPL``."""
    token = (query or "").split()[0] if query else ""
    token = token.strip(".,:;!?()'\"").upper()
    match = _TICKER_TOKEN.fullmatch(token)
    if match is None:
        return None
    return match.group(1)


def parse_within(value: str) -> timedelta | None:
    """``30s``, ``5m``, ``1h``, ``2d``, or a bare unit such as ``minute`` (meaning 1).

    Blank means no window. Anything else raises ``ValueError``.
    """
    text = "".join((value or "").split()).casefold()
    if not text:
        return None
    match = _WITHIN.fullmatch(text)
    if match is None:
        raise ValueError(_WITHIN_ERROR)
    amount = int(match.group(1) or "1")
    if amount < 1:
        raise ValueError(_WITHIN_ERROR)
    try:
        return timedelta(seconds=amount * _SECONDS[match.group(2)])
    except OverflowError as exc:
        raise ValueError(_WITHIN_ERROR) from exc


def format_within(window: timedelta) -> str:
    seconds = int(window.total_seconds())
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def published_at(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def keep_recent(payload: dict[str, Any], window: timedelta, *, now: datetime | None = None) -> dict[str, Any]:
    """Drop headlines older than ``window``, and any headline with no usable date."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - window
    raw = payload.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            published = published_at(str(item.get("published") or ""))
            if published is not None and published >= cutoff:
                items.append(item)
    result = {**payload, "within": format_within(window), "count": len(items), "items": items}
    if items:
        result.pop("error", None)
    return result


def too_short(query: str) -> dict[str, Any]:
    return {"query": query, "count": 0, "items": [], "error": "Query is too short."}


def no_match(query: str) -> dict[str, Any]:
    return {"query": query, "count": 0, "items": []}


def search_failed(query: str, exc: Exception) -> dict[str, Any]:
    return {"query": query, "count": 0, "items": [], "error": f"News search failed: {exc}"}


def unreadable(query: str) -> dict[str, Any]:
    return {"query": query, "count": 0, "items": [], "error": "News feed was not readable."}


def headlines(query: str, items: list[dict[str, str]]) -> dict[str, Any]:
    return {"query": query, "count": len(items), "items": items}


def fetch_xml(
    client: httpx.Client | None,
    url: str,
    params: dict[str, str],
    *,
    headers: dict[str, str] | None = None,
) -> str:
    if client is not None:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.text
    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers or HEADERS) as http:
        response = http.get(url, params=params)
        response.raise_for_status()
        return response.text


def parse_release_rss(xml_text: str, *, limit: int, source: str, series: str) -> list[dict[str, str]]:
    """RSS items for an official release. A summary that only repeats the title is dropped."""
    root = ElementTree.fromstring(xml_text)
    cap = cap_limit(limit)
    items: list[dict[str, str]] = []
    for item in iter_items(root):
        title = child_text(item, "title")
        link = child_text(item, "link")
        if not title or not link.startswith(("http://", "https://")):
            continue
        row = {
            "title": title,
            "source": source,
            "series": series,
            "published": child_text(item, "pubDate"),
            "link": link,
            "summary": story_summary(child_text(item, "description"), title=title),
        }
        items.append({key: value for key, value in row.items() if value})
        if len(items) >= cap:
            break
    return items


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def iter_items(root: ElementTree.Element) -> Iterator[ElementTree.Element]:
    for node in root.iter():
        if local_name(node.tag) == "item":
            yield node


def child_text(item: ElementTree.Element, name: str) -> str:
    wanted = name.casefold()
    for child in item:
        if local_name(child.tag) != wanted:
            continue
        if child.text and child.text.strip():
            return html.unescape(" ".join(child.text.split()))
        href = child.get("href") or child.get("url")
        if href:
            return href.strip()
    return ""
