from __future__ import annotations

import json
from datetime import datetime, timezone

from documents import dedupe, document_id, render_ndjson, to_document

WHEN = datetime(2026, 11, 4, 16, 30, tzinfo=timezone.utc)


def _item(**overrides: str) -> dict[str, str]:
    item = {
        "title": "Fed holds rates",
        "source": "Federal Reserve",
        "published": "Wed, 04 Nov 2026 19:00:00 GMT",
        "link": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261104a.htm",
        "summary": "The FOMC left the target range unchanged.",
    }
    item.update(overrides)
    return item


def test_document_uses_the_link_as_a_stable_id() -> None:
    first = to_document(_item(), feed="federalreserve", category="monetary-policy", symbols=[], collected_at=WHEN)
    second = to_document(_item(summary="A longer summary of the same decision."), feed="google", category="federal reserve", symbols=["SPY"], collected_at=WHEN)
    assert first is not None and second is not None
    assert first["id"] == second["id"]
    assert first["id"] == document_id(url=first["url"], title=first["title"], source=first["source"])
    assert len(first["id"]) == 64


def test_passage_and_dates_match_the_index_contract() -> None:
    document = to_document(_item(), feed="federalreserve", category="Monetary Policy", symbols=["spy"], collected_at=WHEN)
    assert document is not None
    assert document["schema_version"] == 1
    assert document["text"] == "Fed holds rates\n\nThe FOMC left the target range unchanged.\n\nSource: Federal Reserve"
    assert document["published_at"] == "2026-11-04T19:00:00Z"
    assert document["collected_at"] == "2026-11-04T16:30:00Z"
    assert document["collected_on"] == "2026-11-04"
    assert document["category"] == "monetary policy"
    assert document["symbols"] == ["SPY"]
    assert document["summary"] == "The FOMC left the target range unchanged."


def test_blank_summary_and_unreadable_date_are_omitted() -> None:
    document = to_document(
        _item(summary="", published="not-a-date"),
        feed="google",
        category="inflation",
        symbols=[],
        collected_at=WHEN,
    )
    assert document is not None
    assert "summary" not in document
    assert "published_at" not in document
    assert document["text"] == "Fed holds rates\n\nSource: Federal Reserve"


def test_item_without_a_link_is_skipped() -> None:
    assert to_document(_item(link=""), feed="google", category="inflation", symbols=[], collected_at=WHEN) is None


def test_dedupe_keeps_the_longer_passage_and_merges_symbols() -> None:
    short = to_document(_item(summary=""), feed="bing", category="federal reserve", symbols=["SPY"], collected_at=WHEN)
    long = to_document(
        _item(summary="The FOMC left the target range unchanged."),
        feed="google",
        category="federal reserve",
        symbols=["QQQ"],
        collected_at=WHEN,
    )
    assert short is not None and long is not None
    kept = dedupe([short, long])
    assert len(kept) == 1
    assert kept[0]["feed"] == "google"
    assert kept[0]["symbols"] == ["QQQ", "SPY"]


def test_ndjson_is_one_object_per_line() -> None:
    document = to_document(_item(title='Fed says "hold"'), feed="google", category="inflation", symbols=[], collected_at=WHEN)
    assert document is not None
    raw = render_ndjson([document])
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["title"] == 'Fed says "hold"'
