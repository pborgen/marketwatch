from __future__ import annotations

from datetime import date

from agent import filings, headlines, price_history, quote, using_feeds
from datafeed.yahoo.quote import YahooQuote
from evals.books import AAPL_HISTORY, AAPL_QUOTE, FILING_ERROR, FilingBook, NewsBook, QuoteBook


def _story(title: str) -> dict[str, str]:
    return {
        "title": title,
        "published": "Wed, 04 Nov 2026 15:00:00 GMT",
        "link": "https://example.com/" + title.replace(" ", "-"),
        "source": "Example",
    }


def test_quote_keeps_the_brief_fields() -> None:
    row = {**AAPL_QUOTE, "source": "yahoo"}
    with using_feeds(QuoteBook({"AAPL": row}), NewsBook(), NewsBook(), FilingBook()):
        found = quote("nasdaq:aapl")
    assert found["price"] == 190.25
    assert found["name"] == "Apple Inc."
    assert found["delayed"] is True
    assert "source" not in found


def test_price_history_clamps_the_span_and_summarizes() -> None:
    quotes = QuoteBook(histories={"AAPL": AAPL_HISTORY})
    with using_feeds(quotes, NewsBook(), NewsBook(), FilingBook()):
        summary = price_history("AAPL", months=100)
    assert summary["start_price"] == 100
    assert summary["end_price"] == 150
    assert summary["change_pct"] == 50
    assert summary["months"] == 24
    assert summary["delayed"] is True
    _symbol, start, end, interval = quotes.price_calls[0]
    assert interval == "1d"
    assert end == date.today()
    assert (end - start).days == 24 * 30


def test_headlines_keeps_both_sources_and_caps_the_limit() -> None:
    yahoo = NewsBook({"AAPL": [_story("Yahoo headline"), _story("second")]})
    seeking = NewsBook({"AAPL": [_story("Seeking headline")]})
    with using_feeds(QuoteBook(), yahoo, seeking, FilingBook()):
        found = headlines("AAPL", limit=1)
    assert [item["title"] for item in found["items"]] == ["Yahoo headline", "Seeking headline"]
    assert yahoo.limits == [("AAPL", 1)]
    assert seeking.limits == [("AAPL", 1)]


def test_filings_returns_a_stubbed_error() -> None:
    book = FilingBook({"AAPL": {"error": FILING_ERROR}})
    with using_feeds(QuoteBook(), NewsBook(), NewsBook(), book):
        found = filings("AAPL", limit=0)
    assert found == {"symbol": "AAPL", "error": FILING_ERROR}
    assert book.limits == [("AAPL", 1)]


def test_using_feeds_restores_the_previous_clients() -> None:
    from agent import _FEEDS

    with using_feeds(QuoteBook(), NewsBook(), NewsBook(), FilingBook()):
        assert quote("AAPL")["error"]
    assert isinstance(_FEEDS.quotes, YahooQuote)
    assert _FEEDS.filings is None
