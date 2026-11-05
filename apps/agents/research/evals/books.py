"""Frozen quotes, headlines, and filings for evaluation.

The model still decides which tools to call. The tools return this book
instead of Yahoo Finance or EDGAR, so a score is about the agent rather
than whatever the market did that minute.
"""

from __future__ import annotations

from datetime import date
from typing import Any

AAPL_QUOTE: dict[str, Any] = {
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "price": 190.25,
    "currency": "USD",
    "previous_close": 188.0,
    "day_change": 2.25,
    "day_change_pct": 1.1968,
    "exchange": "NMS",
    "volume": 1000,
    "market_cap": 2_800_000_000_000,
    "pe": 30.1,
    "fifty_two_week_high": 260.0,
    "fifty_two_week_low": 164.0,
    "market_state": "CLOSED",
    "as_of": "2026-11-04T21:00:00Z",
    "delayed": True,
}

MSFT_QUOTE: dict[str, Any] = {
    "symbol": "MSFT",
    "name": "Microsoft Corporation",
    "price": 410.5,
    "currency": "USD",
    "previous_close": 405.0,
    "day_change": 5.5,
    "day_change_pct": 1.358,
    "exchange": "NMS",
    "volume": 2000,
    "market_cap": 3_000_000_000_000,
    "pe": 35.0,
    "fifty_two_week_high": 468.0,
    "fifty_two_week_low": 344.0,
    "market_state": "CLOSED",
    "as_of": "2026-11-04T21:00:00Z",
    "delayed": True,
}

AAPL_HISTORY: dict[str, Any] = {
    "symbol": "AAPL",
    "currency": "USD",
    "prices": [
        {"date": "2025-11-05", "price": 100},
        {"date": "2026-05-05", "price": 120},
        {"date": "2026-11-04", "price": 150},
    ],
}

MSFT_HISTORY: dict[str, Any] = {
    "symbol": "MSFT",
    "currency": "USD",
    "prices": [
        {"date": "2025-11-05", "price": 300},
        {"date": "2026-11-04", "price": 360},
    ],
}

FILING_ERROR = "Set SEC_USER_AGENT to a name and email. EDGAR requires it."

_AAPL_NEWS = [
    {
        "title": "Apple ships a new chip",
        "published": "Wed, 04 Nov 2026 15:00:00 GMT",
        "link": "https://example.com/aapl-chip",
        "source": "Example",
    }
]
_MSFT_NEWS = [
    {
        "title": "Microsoft expands its cloud regions",
        "published": "Wed, 04 Nov 2026 15:00:00 GMT",
        "link": "https://example.com/msft-cloud",
        "source": "Example",
    }
]
_AAPL_FILINGS = {
    "items": [
        {
            "form": "10-K",
            "filed": "2025-11-01",
            "description": "Annual report",
            "link": "https://example.com/aapl-10k",
        }
    ]
}
_MSFT_FILINGS = {
    "items": [
        {
            "form": "10-Q",
            "filed": "2026-01-28",
            "description": "Quarterly report",
            "link": "https://example.com/msft-10q",
        }
    ]
}


def _row(mapping: dict[str, Any], symbol: str) -> Any:
    """Match ``AAPL`` when the tool was given ``NASDAQ:AAPL``."""
    if symbol in mapping:
        return mapping[symbol]
    bare = symbol.split(":")[-1]
    if bare in mapping:
        return mapping[bare]
    return None


class QuoteBook:
    def __init__(
        self,
        quotes: dict[str, dict[str, Any]] | None = None,
        histories: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.quotes = quotes or {}
        self.histories = histories or {}
        self.price_calls: list[tuple[str, date, date, str]] = []

    def quote(self, symbol: str) -> dict[str, Any]:
        row = _row(self.quotes, symbol)
        if row is None:
            return {"symbol": symbol, "error": f"No quote for {symbol}."}
        return dict(row)

    def prices(self, symbol: str, *, start: date, end: date, interval: str) -> dict[str, Any]:
        self.price_calls.append((symbol, start, end, interval))
        found = _row(self.histories, symbol)
        if found is None:
            return {"symbol": symbol, "error": f"No price history for {symbol}."}
        return dict(found)


class NewsBook:
    def __init__(self, stories: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.stories = stories or {}
        self.limits: list[tuple[str, int]] = []

    def search(self, query: str, *, limit: int) -> dict[str, Any]:
        self.limits.append((query, limit))
        items = _row(self.stories, query)
        return {"items": list(items or [])[:limit]}


class FilingBook:
    def __init__(self, filings: dict[str, dict[str, Any]] | None = None) -> None:
        self.rows = filings or {}
        self.limits: list[tuple[str, int]] = []

    def filings(self, symbol: str, *, limit: int) -> dict[str, Any]:
        self.limits.append((symbol, limit))
        found = _row(self.rows, symbol)
        if found is None:
            return {"symbol": symbol, "error": f"No filings for {symbol}."}
        return found


def book(name: str) -> tuple[QuoteBook, NewsBook, NewsBook, FilingBook]:
    """One named stand-in feed. ``compare`` has two tickers. ``filings-down`` errors on EDGAR."""
    if name == "compare":
        quotes = {"AAPL": AAPL_QUOTE, "MSFT": MSFT_QUOTE}
        histories = {"AAPL": AAPL_HISTORY, "MSFT": MSFT_HISTORY}
        stories = {"AAPL": _AAPL_NEWS, "MSFT": _MSFT_NEWS}
        filings = {"AAPL": _AAPL_FILINGS, "MSFT": _MSFT_FILINGS}
    elif name == "filings-down":
        quotes = {"AAPL": AAPL_QUOTE}
        histories = {"AAPL": AAPL_HISTORY}
        stories = {"AAPL": _AAPL_NEWS}
        filings = {"AAPL": {"error": FILING_ERROR}}
    elif name == "empty":
        quotes = {}
        histories = {}
        stories = {}
        filings = {}
    else:
        quotes = {"AAPL": AAPL_QUOTE}
        histories = {"AAPL": AAPL_HISTORY}
        stories = {"AAPL": _AAPL_NEWS}
        filings = {"AAPL": _AAPL_FILINGS}
    return QuoteBook(quotes, histories), NewsBook(stories), NewsBook(stories), FilingBook(filings)
