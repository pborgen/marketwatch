from __future__ import annotations

import json
from datetime import datetime, timezone

from collect import Feeds, run_collection, topic_symbol
from store import events_key

WHEN = datetime(2026, 11, 4, 16, 30, tzinfo=timezone.utc)
LINK = "https://example.com/fed-holds"


class Search:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {"items": []}
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, *, limit: int) -> dict:
        self.queries.append((query, limit))
        if callable(self.payload):
            return self.payload(query)
        return self.payload


class Releases:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {"items": []}
        self.calls = 0

    def releases(self, *, limit: int) -> dict:
        self.calls += 1
        return self.payload


class Bucket:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_object(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {}


def _feeds(**overrides: object) -> Feeds:
    values: dict[str, object] = {
        "google": Search(),
        "bing": Search(),
        "yahoo": Search(),
        "nasdaq": Search(),
        "seeking_alpha": Search(),
        "federal_reserve": Releases(),
        "bls": Releases(),
    }
    values.update(overrides)
    return Feeds(**values)


def _story(title: str, link: str, summary: str = "") -> dict[str, str]:
    return {
        "title": title,
        "source": "Example",
        "published": "Wed, 04 Nov 2026 15:00:00 GMT",
        "link": link,
        "summary": summary,
    }


def test_phrase_topics_are_not_tickers() -> None:
    assert topic_symbol("stock market") is None
    assert topic_symbol("AAPL") == "AAPL"
    assert topic_symbol("NASDAQ:MSFT") == "MSFT"


def test_collection_writes_ndjson_under_the_utc_date() -> None:
    google = Search({"items": [_story("Fed holds rates", LINK, "The target range was unchanged.")]})
    bing = Search({"items": [_story("Fed holds rates", LINK, "Short")]})
    fed = Releases(
        {
            "items": [
                _story(
                    "FOMC statement",
                    "https://www.federalreserve.gov/statement",
                    "Rates unchanged.",
                )
            ]
        }
    )
    bls = Releases({"items": [], "error": "Release feed failed: HTTP 503"})
    feeds = _feeds(google=google, bing=bing, federal_reserve=fed, bls=bls)
    bucket = Bucket()
    result = run_collection(
        "inflation",
        limit=3,
        feeds=feeds,
        bucket="market-data",
        client=bucket,
        now=WHEN,
    )

    assert google.queries == [("inflation", 3)]
    assert feeds.yahoo.queries == []
    assert result["stored"] is True
    assert result["count"] == 2
    assert result["uri"] == "s3://market-data/current-events/date=2026-11-04/events-20261104T163000Z.ndjson"
    assert result["index"] == "current-events"
    assert result["text_field"] == "text"
    assert result["errors"] == ["bls: Release feed failed: HTTP 503"]
    assert result["feeds"]["google"] == 1
    assert result["feeds"]["federalreserve"] == 1
    assert len(bucket.calls) == 1
    put = bucket.calls[0]
    assert put["Bucket"] == "market-data"
    assert put["Key"] == events_key(WHEN)
    assert put["ContentType"] == "application/x-ndjson"
    lines = put["Body"].decode("utf-8").splitlines()
    assert len(lines) == 2
    stored = json.loads(lines[0])
    assert stored["text"].startswith("Fed holds rates")
    assert "target range" in stored["text"]
    assert stored["collected_on"] == "2026-11-04"


def test_ticker_topic_queries_ticker_feeds() -> None:
    yahoo = Search({"items": [_story("Apple update", "https://example.com/aapl")]})
    feeds = _feeds(yahoo=yahoo)
    bucket = Bucket()
    result = run_collection(
        "AAPL",
        include_releases=False,
        feeds=feeds,
        bucket="market-data",
        client=bucket,
        now=WHEN,
    )
    assert yahoo.queries == [("AAPL", 8)]
    assert feeds.nasdaq.queries == [("AAPL", 8)]
    assert feeds.seeking_alpha.queries == [("AAPL", 8)]
    assert feeds.federal_reserve.calls == 0
    assert result["count"] == 1
    stored = json.loads(bucket.calls[0]["Body"].decode("utf-8").splitlines()[0])
    assert stored["symbols"] == ["AAPL"]


def test_empty_collection_does_not_write() -> None:
    bucket = Bucket()
    result = run_collection("inflation", feeds=_feeds(), bucket="market-data", client=bucket, now=WHEN)
    assert result["stored"] is False
    assert result["count"] == 0
    assert bucket.calls == []


def test_missing_bucket_is_an_error() -> None:
    result = run_collection("inflation", feeds=_feeds(), bucket="", now=WHEN)
    assert result["error"] == "Set DATA_BUCKET to the S3 bucket that stores current events."
