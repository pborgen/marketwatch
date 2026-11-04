"""TradingView public scanner quote. No session cookie.

Price, name, day change, sector, industry, volume, market cap, P/E, and
technical rating. ``update_mode`` says when the print is delayed.
"""

from __future__ import annotations

from typing import Any

import httpx

from datafeed.http import (
    QuoteLookupError,
    TV_HEADERS,
    failed,
    request_json,
    round_number,
    row,
    whole_number,
    with_client,
)
from datafeed.parse import parse_quotes

URL = "https://scanner.tradingview.com/{market}/scan"
SOURCE = "tradingview"
SCAN_COLUMNS = [
    "name",
    "description",
    "close",
    "change",
    "change_abs",
    "Recommend.All",
    "sector",
    "industry",
    "volume",
    "market_cap_basic",
    "price_earnings_ttm",
    "update_mode",
]


def _delayed(update_mode: str | None) -> bool:
    mode = (update_mode or "").casefold()
    if not mode:
        return True
    return "delayed" in mode


def _rows(payload: dict[str, Any]) -> list[Any]:
    rows = payload.get("data")
    return rows if isinstance(rows, list) else []


def tradingview_quote(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    quotes = parse_quotes(payload, list(SCAN_COLUMNS))
    quote = quotes.get(symbol)
    if quote is None and quotes:
        quote = next(iter(quotes.values()))
    if quote is None or quote.close is None:
        return failed(SOURCE, "No public quote.")
    return row(
        SOURCE,
        symbol=quote.symbol,
        name=quote.name,
        price=round_number(quote.close),
        day_change=round_number(quote.change_abs),
        day_change_pct=round_number(quote.change_pct),
        technical_rating=quote.rating,
        technical_score=round_number(quote.recommend),
        sector=quote.sector,
        industry=quote.industry,
        volume=whole_number(quote.volume),
        market_cap=whole_number(quote.market_cap),
        pe=round_number(quote.pe),
        delayed=_delayed(quote.update_mode),
    )


def _scan(http: httpx.Client, market: str, body: dict[str, Any]) -> dict[str, Any]:
    return request_json(http, "POST", URL.format(market=market), json=body, headers=TV_HEADERS)


def _fetch(http: httpx.Client, symbol: str) -> dict[str, Any]:
    columns = list(SCAN_COLUMNS)
    if ":" in symbol:
        body = {"symbols": {"tickers": [symbol], "query": {"types": []}}, "columns": columns}
        return _scan(http, "global", body)
    body = {
        "filter": [{"left": "name", "operation": "equal", "right": symbol}],
        "columns": columns,
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 1],
    }
    payload = _scan(http, "america", body)
    if _rows(payload):
        return payload
    return _scan(http, "global", body)


class TradingViewQuote:
    name = SOURCE

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def quote(self, symbol: str) -> dict[str, Any]:
        try:
            payload = with_client(self._client, lambda http: _fetch(http, symbol))
        except QuoteLookupError as exc:
            return failed(SOURCE, str(exc))
        return tradingview_quote(symbol, payload)
