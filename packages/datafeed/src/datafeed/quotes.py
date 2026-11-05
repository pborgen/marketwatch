"""Try every feed that can return a quote, and keep the first price.

A rate limit or a miss from one vendor is an error on that vendor. The next
quote feed is tried. ``feeds_for(DataKind.QUOTE)`` sets the order: Nasdaq,
then TradingView, then Yahoo.
"""

from __future__ import annotations

from typing import Any

from datafeed.kinds import DataKind, feeds_for
from datafeed.nasdaq.quote import NasdaqQuote
from datafeed.tradingview.quote import TradingViewQuote
from datafeed.yahoo.quote import YahooQuote

_CLIENTS: dict[str, type] = {
    "nasdaq": NasdaqQuote,
    "tradingview": TradingViewQuote,
    "yahoo": YahooQuote,
}


def quote_clients() -> list[type]:
    """Client classes for the feeds that declare ``DataKind.QUOTE``, in feed order."""
    clients: list[type] = []
    for feed in feeds_for(DataKind.QUOTE):
        client = _CLIENTS.get(feed.name)
        if client is None:
            raise RuntimeError(f"{feed.name} declares quotes but has no quote client.")
        clients.append(client)
    return clients


class QuoteService:
    """One ``quote`` call walks the quote feeds until a price comes back."""

    def __init__(self, clients: list[Any] | None = None) -> None:
        self._clients = list(clients) if clients is not None else [client() for client in quote_clients()]

    def quote(self, symbol: str) -> dict[str, Any]:
        failures: list[dict[str, str]] = []
        for client in self._clients:
            row = client.quote(symbol)
            if isinstance(row, dict) and not row.get("error") and row.get("price") is not None:
                return row
            source = getattr(client, "name", None)
            message = "No quote."
            if isinstance(row, dict):
                source = source or row.get("source")
                if row.get("error"):
                    message = str(row["error"])
            failures.append({"source": str(source or "unknown"), "error": message})
        return {
            "symbol": symbol,
            "error": "No quote feed returned a price.",
            "failures": failures,
        }
