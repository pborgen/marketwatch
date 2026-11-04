"""Seeking Alpha ticker feed. Titles, authors, and dates. No API key.

Analysis items link to the article. News items share the symbol page, so the
guid is added to the link and the stories stay distinct. A query with no
ticker skips the network. The feed does not include the article body.
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

URL = "https://seekingalpha.com/api/sa/combined/{ticker}.xml"


def _link(item: ElementTree.Element) -> str:
    link = child_text(item, "link")
    guid = child_text(item, "guid")
    if "/symbol/" in link and guid:
        ident = guid.rsplit(":", 1)[-1]
        if ident and ident not in link:
            return f"{link}#{ident}"
    return link


def parse_seeking_alpha_rss(xml_text: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, str]]:
    root = ElementTree.fromstring(xml_text)
    items: list[dict[str, str]] = []
    cap = cap_limit(limit)
    for item in iter_items(root):
        title = child_text(item, "title")
        link = _link(item)
        if not title or not link.startswith(("http://", "https://")):
            continue
        items.append(
            {
                "title": title,
                "source": child_text(item, "author_name") or "Seeking Alpha",
                "published": child_text(item, "pubDate"),
                "link": link,
                "summary": story_summary(child_text(item, "description"), title=title),
            }
        )
        if len(items) >= cap:
            break
    return items


class SeekingAlphaRss:
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
        try:
            xml_text = fetch_xml(self._client, URL.format(ticker=ticker), {})
        except httpx.HTTPError as exc:
            return search_failed(cleaned, exc)
        try:
            items = parse_seeking_alpha_rss(xml_text, limit=cap)
        except ElementTree.ParseError:
            return unreadable(cleaned)
        return headlines(cleaned, items)
