"""Google News RSS. Titles, sources, dates, and the feed summary. No API key.

Google's summary is usually a repeat of the title, so that field is often empty.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

import httpx

from datafeed.rss import (
    DEFAULT_LIMIT,
    cap_limit,
    child_text,
    clean_query,
    fetch_xml,
    headlines,
    iter_items,
    search_failed,
    story_summary,
    too_short,
    unreadable,
)

URL = "https://news.google.com/rss/search"


def parse_google_rss(xml_text: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, str]]:
    root = ElementTree.fromstring(xml_text)
    items: list[dict[str, str]] = []
    cap = cap_limit(limit)
    for item in iter_items(root):
        title = child_text(item, "title")
        link = child_text(item, "link")
        if not title or not link.startswith(("http://", "https://")):
            continue
        items.append(
            {
                "title": title,
                "source": child_text(item, "source") or "Google News",
                "published": child_text(item, "pubDate"),
                "link": link,
                "summary": story_summary(child_text(item, "description"), title=title),
            }
        )
        if len(items) >= cap:
            break
    return items


class GoogleNewsRss:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def search(self, query: str, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        cleaned = clean_query(query)
        if len(cleaned) < 2:
            return too_short(cleaned)
        cap = cap_limit(limit)
        params = {"q": cleaned, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        try:
            xml_text = fetch_xml(self._client, URL, params)
        except httpx.HTTPError as exc:
            return search_failed(cleaned, exc)
        try:
            items = parse_google_rss(xml_text, limit=cap)
        except ElementTree.ParseError:
            return unreadable(cleaned)
        return headlines(cleaned, items)
