from __future__ import annotations

from datafeed.bing.feed import Bing
from datafeed.kinds import DataKind, all_feeds, feeds_for
from datafeed.quotes import QuoteService, quote_clients
from datafeed.tradingview.feed import TradingView
from datafeed.yahoo.feed import Yahoo


def test_bing_reports_headlines_only() -> None:
    assert Bing.name == "bing"
    assert Bing.kinds() == frozenset({DataKind.HEADLINES})


def test_yahoo_reports_every_kind_it_fetches() -> None:
    assert Yahoo.kinds() == frozenset({DataKind.HEADLINES, DataKind.QUOTE, DataKind.PRICE_HISTORY})


def test_feeds_for_returns_every_feed_that_shares_a_kind() -> None:
    headlines = [feed.name for feed in feeds_for(DataKind.HEADLINES)]
    assert headlines == ["bing", "google", "nasdaq", "seekingalpha", "yahoo"]
    assert [feed.name for feed in feeds_for(DataKind.QUOTE)] == ["nasdaq", "tradingview", "yahoo"]
    assert [feed.name for feed in feeds_for(DataKind.PRICE_HISTORY)] == ["nasdaq", "yahoo"]
    assert [feed.name for feed in feeds_for(DataKind.SCREEN)] == ["tradingview"]
    assert [feed.name for feed in feeds_for(DataKind.FILING)] == ["edgar"]
    assert [feed.name for feed in feeds_for(DataKind.RELEASE)] == ["bls", "federalreserve"]


def test_quote_clients_follow_the_quote_feeds() -> None:
    assert [client.name for client in quote_clients()] == ["nasdaq", "tradingview", "yahoo"]


class _Limited:
    name = "yahoo"

    def quote(self, symbol: str) -> dict[str, str]:
        return {"source": "yahoo", "error": "HTTP 429"}


class _Priced:
    name = "nasdaq"

    def quote(self, symbol: str) -> dict[str, object]:
        return {"source": "nasdaq", "symbol": symbol, "price": 10}


class _Empty:
    name = "tradingview"

    def quote(self, symbol: str) -> dict[str, str]:
        return {"source": "tradingview", "error": "No public quote."}


def test_quote_service_skips_a_rate_limit() -> None:
    row = QuoteService([_Limited(), _Priced()]).quote("AAPL")
    assert row == {"source": "nasdaq", "symbol": "AAPL", "price": 10}


def test_quote_service_reports_every_failure() -> None:
    row = QuoteService([_Limited(), _Empty()]).quote("AAPL")
    assert row["error"] == "No quote feed returned a price."
    assert row["failures"] == [
        {"source": "yahoo", "error": "HTTP 429"},
        {"source": "tradingview", "error": "No public quote."},
    ]


def test_every_feed_declares_at_least_one_kind() -> None:
    assert all_feeds()
    assert TradingView in all_feeds()
    for feed in all_feeds():
        assert feed.name
        assert feed.kinds()
        assert feed.kinds() <= set(DataKind)
