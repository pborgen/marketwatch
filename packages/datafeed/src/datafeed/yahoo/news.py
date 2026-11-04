"""Yahoo Finance ticker RSS. Titles and dates. No API key.

The feed is per ticker and does not name an outlet, so items are labeled
Yahoo Finance. A query with no ticker skips the network.
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
    no_match,
    search_failed,
    story_summary,
    ticker_from_query,
    too_short,
    unreadable,
)

URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"


def parse_yahoo_rss(xml_text: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, str]]:
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
                "source": "Yahoo Finance",
                "published": child_text(item, "pubDate"),
                "link": link,
                "summary": story_summary(child_text(item, "description"), title=title),
            }
        )
        if len(items) >= cap:
            break
    return items


class YahooFinanceRss:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def search(self, query: str, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        cleaned = clean_query(query)
        if len(cleaned) < 2:
            return too_short(cleaned)
        ticker = ticker_from_query(cleaned)
        if ticker is None:
            return no_match(cleaned)
        cap = cap_limit(limit)
        params = {"s": ticker, "region": "US", "lang": "en-US"}
        try:
            xml_text = fetch_xml(self._client, URL, params)
        except httpx.HTTPError as exc:
            return search_failed(cleaned, exc)
        try:
            items = parse_yahoo_rss(xml_text, limit=cap)
        except ElementTree.ParseError:
            return unreadable(cleaned)
        return headlines(cleaned, items)
