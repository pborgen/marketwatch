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

def test_quote_pass() -> None:
    h = quote("AAPL")
    assert h["symbol"] == "AAPL"
    assert h["name"] == "Apple Inc."
    assert h["price"] == 150.00
    assert h["currency"] == "USD"
    assert h["previous_close"] == 145.00
    assert h["day_change"] == 5.00
    assert h["day_change_pct"] == 0.0345
    assert h["exchange"] == "NASDAQ"
    assert h["volume"] == 1000000
    assert h["market_cap"] == 1000000000000
    assert h["pe"] == 20.00