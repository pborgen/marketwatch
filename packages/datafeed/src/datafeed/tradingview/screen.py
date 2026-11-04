"""US common stocks that look cheap on trailing P/E and price-to-book.

The TradingView public scanner supplies the ratios. A low pair of ratios is
a research list. It is not a reason to trade.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from datafeed.http import (
    TV_HEADERS,
    QuoteLookupError,
    request_json,
    round_number,
    whole_number,
    with_client,
)

URL = "https://scanner.tradingview.com/america/scan"
SOURCE = "tradingview"
DEFAULT_LIMIT = 15
MAX_LIMIT = 40
DEFAULT_MAX_PE = 15.0
DEFAULT_MAX_PB = 2.5
DEFAULT_MIN_MARKET_CAP = 2_000_000_000
MIN_VOLUME = 100_000
_EXCHANGES = ["NYSE", "NASDAQ", "AMEX"]
_COLUMNS = [
    "name",
    "description",
    "close",
    "price_earnings_ttm",
    "price_book_fq",
    "price_sales_current",
    "dividends_yield",
    "market_cap_basic",
    "sector",
    "volume",
    "exchange",
]


class ValueSource(Protocol):
    def screen(
        self,
        *,
        limit: int = DEFAULT_LIMIT,
        max_pe: float = DEFAULT_MAX_PE,
        max_price_to_book: float = DEFAULT_MAX_PB,
        min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
    ) -> dict[str, Any]: ...


def cap_limit(limit: int) -> int:
    try:
        cap = int(limit or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        cap = DEFAULT_LIMIT
    return max(1, min(cap, MAX_LIMIT))


def _positive(value: Any, *, upper: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number > upper:
        return None
    return number


def _market_cap_floor(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _rules(max_pe: float, max_price_to_book: float, min_market_cap: float) -> dict[str, Any]:
    return {
        "market": "america",
        "listing": "common stock",
        "exchanges": list(_EXCHANGES),
        "max_pe": max_pe,
        "max_price_to_book": max_price_to_book,
        "min_market_cap": int(min_market_cap),
        "min_volume": MIN_VOLUME,
    }


def _body(limit: int, max_pe: float, max_price_to_book: float, min_market_cap: float) -> dict[str, Any]:
    return {
        "filter": [
            {"left": "type", "operation": "equal", "right": "stock"},
            {"left": "subtype", "operation": "equal", "right": "common"},
            {"left": "exchange", "operation": "in_range", "right": list(_EXCHANGES)},
            {"left": "market_cap_basic", "operation": "egreater", "right": min_market_cap},
            {"left": "price_earnings_ttm", "operation": "in_range", "right": [0.1, max_pe]},
            {"left": "price_book_fq", "operation": "in_range", "right": [0.1, max_price_to_book]},
            {"left": "volume", "operation": "egreater", "right": MIN_VOLUME},
        ],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": list(_COLUMNS),
        "sort": {"sortBy": "price_earnings_ttm", "sortOrder": "asc"},
        "range": [0, limit],
    }


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def _item(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    ticker = _text(entry.get("s"))
    values = entry.get("d")
    if ticker is None or not isinstance(values, list) or len(values) < len(_COLUMNS):
        return None
    fields = dict(zip(_COLUMNS, values, strict=False))
    symbol = _text(fields["name"])
    if symbol is None or "/" in symbol or "/" in ticker:
        return None
    pe = round_number(fields["price_earnings_ttm"])
    price_to_book = round_number(fields["price_book_fq"])
    if pe is None or price_to_book is None or pe <= 0 or price_to_book <= 0:
        return None
    item: dict[str, Any] = {
        "ticker": ticker,
        "symbol": symbol,
        "pe": pe,
        "price_to_book": price_to_book,
        "source": SOURCE,
    }
    name = _text(fields["description"])
    if name is not None:
        item["name"] = name
    price = round_number(fields["close"])
    if price is not None:
        item["price"] = price
    price_to_sales = round_number(fields["price_sales_current"])
    if price_to_sales is not None:
        item["price_to_sales"] = price_to_sales
    dividend_yield = round_number(fields["dividends_yield"])
    if dividend_yield is not None:
        item["dividend_yield_pct"] = dividend_yield
    market_cap = whole_number(fields["market_cap_basic"])
    if market_cap is not None:
        item["market_cap"] = market_cap
    sector = _text(fields["sector"])
    if sector is not None:
        item["sector"] = sector
    volume = whole_number(fields["volume"])
    if volume is not None:
        item["volume"] = volume
    exchange = _text(fields["exchange"])
    if exchange is not None:
        item["exchange"] = exchange
    return item


def _empty(rules: dict[str, Any], *, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"count": 0, "total": 0, "items": [], "screen": rules}
    if error:
        payload["error"] = error
    return payload


class UndervaluedScreen:
    """Lowest trailing P/E first, among names that also clear the book-value cap."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def screen(
        self,
        *,
        limit: int = DEFAULT_LIMIT,
        max_pe: float = DEFAULT_MAX_PE,
        max_price_to_book: float = DEFAULT_MAX_PB,
        min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
    ) -> dict[str, Any]:
        cap = cap_limit(limit)
        pe = _positive(max_pe, upper=100)
        book = _positive(max_price_to_book, upper=20)
        market_cap = _market_cap_floor(min_market_cap)
        if pe is None or book is None or market_cap is None:
            return _empty(
                _rules(DEFAULT_MAX_PE, DEFAULT_MAX_PB, DEFAULT_MIN_MARKET_CAP),
                error="max_pe and max_price_to_book must be positive, and min_market_cap cannot be negative.",
            )
        rules = _rules(pe, book, market_cap)
        try:
            payload = with_client(
                self._client,
                lambda http: request_json(http, "POST", URL, json=_body(cap, pe, book, market_cap), headers=TV_HEADERS),
            )
        except QuoteLookupError as exc:
            return _empty(rules, error=str(exc))
        rows = payload.get("data")
        items = []
        if isinstance(rows, list):
            for entry in rows:
                item = _item(entry)
                if item is not None:
                    items.append(item)
        total = payload.get("totalCount")
        found = total if isinstance(total, int) and total >= 0 else len(items)
        return {"count": len(items), "total": found, "items": items, "screen": rules}
