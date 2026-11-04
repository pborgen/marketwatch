"""Collect current events and store them as OpenSearch documents.

Run it without the model, from the repo root:

    DATA_BUCKET=your-bucket .venv/bin/python apps/agents/current_events/collect.py
    DATA_BUCKET=your-bucket .venv/bin/python apps/agents/current_events/collect.py "oil prices, OPEC"

The object key carries the UTC date. Each line is one document for the
``current-events`` index: embed ``text``, and use ``id`` as the document id.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from datafeed.bing.news import BingNewsRss
from datafeed.bls.releases import BlsReleases
from datafeed.federalreserve.releases import FederalReserveReleases
from datafeed.google.news import GoogleNewsRss
from datafeed.nasdaq.news import NasdaqRss
from datafeed.rss import ticker_from_query
from datafeed.seekingalpha.news import SeekingAlphaRss
from datafeed.yahoo.news import YahooFinanceRss

from documents import INDEX_NAME, dedupe, to_document
from store import bucket_name, prefix_name, s3_client, store_events

DEFAULT_TOPICS = (
    "stock market",
    "Federal Reserve",
    "inflation",
    "US economy",
    "corporate earnings",
)
MAX_TOPICS = 8
DEFAULT_LIMIT = 8
MAX_LIMIT = 20
BROAD_FEEDS = ("google", "bing")
TICKER_FEEDS = ("yahoo", "nasdaq", "seeking_alpha")


@dataclass
class Feeds:
    """Headline search and official-release clients."""

    google: Any
    bing: Any
    yahoo: Any
    nasdaq: Any
    seeking_alpha: Any
    federal_reserve: Any
    bls: Any


def default_feeds() -> Feeds:
    return Feeds(
        google=GoogleNewsRss(),
        bing=BingNewsRss(),
        yahoo=YahooFinanceRss(),
        nasdaq=NasdaqRss(),
        seeking_alpha=SeekingAlphaRss(),
        federal_reserve=FederalReserveReleases(),
        bls=BlsReleases(),
    )


def run_collection(
    topics: str = "",
    limit: int = DEFAULT_LIMIT,
    *,
    include_releases: bool = True,
    feeds: Feeds | None = None,
    bucket: str | None = None,
    client: Any = None,
    now: datetime | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Fetch events, then write newline-delimited JSON to the date prefix."""
    chosen = topic_list(topics)
    if chosen is None:
        return {"error": "Give each topic at least two characters, separated by commas."}
    destination = bucket_name(bucket)
    if not destination:
        return {"error": "Set DATA_BUCKET to the S3 bucket that stores current events."}

    moment = now or datetime.now(timezone.utc)
    cap = _limit(limit)
    clients = feeds or default_feeds()
    errors: list[str] = []
    documents = _gather(clients, chosen, cap, include_releases, moment, errors)
    kept = dedupe(documents)
    if not kept:
        return {
            "stored": False,
            "count": 0,
            "collected_on": _day(moment),
            "errors": errors,
            "index": INDEX_NAME,
        }

    saved = store_events(
        kept,
        bucket=destination,
        client=client or s3_client(),
        when=moment,
        prefix=prefix_name(prefix),
    )
    if saved.get("error"):
        saved["errors"] = errors
        return saved
    counts: dict[str, int] = {}
    for document in kept:
        counts[document["feed"]] = counts.get(document["feed"], 0) + 1
    saved.update(
        {
            "stored": True,
            "index": INDEX_NAME,
            "format": "ndjson",
            "text_field": "text",
            "id_field": "id",
            "feeds": counts,
            "errors": errors,
            "titles": [document["title"] for document in kept[:5]],
        }
    )
    return saved


def topic_list(value: str | None) -> list[str] | None:
    """Comma-separated subjects. Blank selects the default market topics."""
    if value is None or not value.strip():
        return list(DEFAULT_TOPICS)
    chosen: list[str] = []
    folded = set()
    for part in value.split(","):
        topic = " ".join(part.split())
        key = topic.casefold()
        if len(topic) < 2 or key in folded:
            continue
        folded.add(key)
        chosen.append(topic)
        if len(chosen) >= MAX_TOPICS:
            break
    return chosen or None


def topic_symbol(topic: str) -> str | None:
    """A ticker only when the whole topic is one, so 'stock market' stays a phrase."""
    text = " ".join(topic.split())
    if " " in text:
        return None
    return ticker_from_query(text)


def _gather(
    feeds: Feeds,
    topics: list[str],
    limit: int,
    include_releases: bool,
    collected_at: datetime,
    errors: list[str],
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for topic in topics:
        symbol = topic_symbol(topic)
        symbols = [symbol] if symbol else []
        names = BROAD_FEEDS + (TICKER_FEEDS if symbol else ())
        for name in names:
            payload = _search(getattr(feeds, name), name, topic, limit, errors)
            documents.extend(
                _documents(payload, feed=name, category=topic, symbols=symbols, collected_at=collected_at)
            )
    if include_releases:
        documents.extend(_release_documents(feeds.federal_reserve, "federalreserve", limit, collected_at, errors))
        documents.extend(_release_documents(feeds.bls, "bls", limit, collected_at, errors))
    return documents


def _documents(
    payload: dict[str, Any],
    *,
    feed: str,
    category: str,
    symbols: list[str],
    collected_at: datetime,
) -> list[dict[str, Any]]:
    raw = payload.get("items")
    if not isinstance(raw, list):
        return []
    documents: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = _text(item.get("series")) or category
        document = to_document(item, feed=feed, category=label, symbols=symbols, collected_at=collected_at)
        if document is not None:
            documents.append(document)
    return documents


def _release_documents(
    feed: Any,
    name: str,
    limit: int,
    collected_at: datetime,
    errors: list[str],
) -> list[dict[str, Any]]:
    try:
        payload = feed.releases(limit=limit)
    except Exception as exc:
        errors.append(f"{name}: {exc}")
        return []
    if not isinstance(payload, dict):
        errors.append(f"{name}: unreadable result")
        return []
    error = payload.get("error")
    if error:
        errors.append(f"{name}: {error}")
    return _documents(payload, feed=name, category=name, symbols=[], collected_at=collected_at)


def _search(feed: Any, name: str, query: str, limit: int, errors: list[str]) -> dict[str, Any]:
    try:
        payload = feed.search(query, limit=limit)
    except Exception as exc:
        errors.append(f"{name}: {exc}")
        return {"items": []}
    if not isinstance(payload, dict):
        errors.append(f"{name}: unreadable result")
        return {"items": []}
    error = payload.get("error")
    if error:
        errors.append(f"{name}: {error}")
    return payload


def _limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _day(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def main(argv: list[str]) -> None:
    topics = argv[0] if argv else ""
    result = run_collection(topics)
    print(json.dumps(result, indent=2))
    failed = bool(result.get("error")) or (result.get("stored") is False and result.get("count") == 0)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
