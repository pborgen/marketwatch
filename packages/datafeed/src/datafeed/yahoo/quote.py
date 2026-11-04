"""Yahoo Finance chart quote. No API key.

Last price, previous close, currency, exchange, volume, and the 52-week
range come from the chart metadata. The unauthenticated endpoint is delayed,
so this source never claims to be a live tape.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx

from datafeed.http import (
    QuoteLookupError,
    failed,
    request_json,
    round_number,
    row,
    timestamp,
    whole_number,
    with_client,
)

URLS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
)
SOURCE = "yahoo"
_PARAMS = {"range": "1d", "interval": "1d", "includePrePost": "false"}


def chart_symbol(symbol: str) -> str:
    """Yahoo uses a dash for class shares (BRK.B → BRK-B) and no exchange prefix."""
    return symbol.split(":")[-1].replace(".", "-")


def _text(meta: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def yahoo_quote(payload: dict[str, Any]) -> dict[str, Any]:
    chart = payload.get("chart") if isinstance(payload.get("chart"), dict) else {}
    result = chart.get("result")
    meta_row = result[0] if isinstance(result, list) and result and isinstance(result[0], dict) else None
    if meta_row is None:
        error = chart.get("error") if isinstance(chart.get("error"), dict) else {}
        detail = str(error.get("description") or error.get("code") or "").strip()
        return failed(SOURCE, detail or "No public quote.")
    meta = meta_row.get("meta") if isinstance(meta_row.get("meta"), dict) else {}
    price = round_number(meta.get("regularMarketPrice"))
    if price is None:
        return failed(SOURCE, "No public quote.")
    previous = round_number(meta.get("previousClose"))
    if previous is None:
        previous = round_number(meta.get("chartPreviousClose"))
    change = None
    change_pct = None
    if previous not in (None, 0):
        change = round(price - previous, 4)
        change_pct = round(change / abs(previous) * 100, 4)
    return row(
        SOURCE,
        symbol=_text(meta, "symbol"),
        name=_text(meta, "longName", "shortName"),
        instrument=_text(meta, "instrumentType", "quoteType"),
        price=price,
        currency=_text(meta, "currency"),
        previous_close=previous,
        day_change=change,
        day_change_pct=change_pct,
        exchange=_text(meta, "fullExchangeName", "exchangeName"),
        volume=whole_number(meta.get("regularMarketVolume")),
        market_cap=whole_number(meta.get("marketCap")),
        pe=round_number(meta.get("trailingPE")),
        fifty_two_week_high=round_number(meta.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=round_number(meta.get("fiftyTwoWeekLow")),
        market_state=_text(meta, "marketState"),
        as_of=timestamp(meta.get("regularMarketTime")),
        delayed=True,
    )


def _fetch_chart(http: httpx.Client, symbol: str, params: dict[str, str]) -> dict[str, Any]:
    yahoo = chart_symbol(symbol)
    last = "network error"
    for template in URLS:
        try:
            return request_json(http, "GET", template.format(symbol=yahoo), params=params)
        except QuoteLookupError as exc:
            last = str(exc)
            if "429" not in last and "network" not in last:
                raise
    raise QuoteLookupError(last)


def _fetch(http: httpx.Client, symbol: str) -> dict[str, Any]:
    return _fetch_chart(http, symbol, _PARAMS)


def yahoo_prices(payload: dict[str, Any]) -> dict[str, Any]:
    """Close for each bar in a Yahoo chart, oldest first."""
    chart = payload.get("chart") if isinstance(payload.get("chart"), dict) else {}
    result = chart.get("result")
    meta_row = result[0] if isinstance(result, list) and result and isinstance(result[0], dict) else None
    if meta_row is None:
        error = chart.get("error") if isinstance(chart.get("error"), dict) else {}
        detail = str(error.get("description") or error.get("code") or "").strip()
        return failed(SOURCE, detail or "No price history.")
    meta = meta_row.get("meta") if isinstance(meta_row.get("meta"), dict) else {}
    timestamps = meta_row.get("timestamp") if isinstance(meta_row.get("timestamp"), list) else []
    indicators = meta_row.get("indicators") if isinstance(meta_row.get("indicators"), dict) else {}
    quotes = indicators.get("quote") if isinstance(indicators.get("quote"), list) else []
    closes = quotes[0].get("close") if quotes and isinstance(quotes[0], dict) else []
    if not isinstance(closes, list):
        closes = []
    prices: list[dict[str, Any]] = []
    for stamp, close in zip(timestamps, closes):
        price = round_number(close)
        if price is None:
            continue
        try:
            day = datetime.fromtimestamp(int(stamp), timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            continue
        prices.append({"date": day, "price": price})
    if not prices:
        return failed(SOURCE, "No price history.")
    return row(
        SOURCE,
        symbol=_text(meta, "symbol"),
        currency=_text(meta, "currency"),
        prices=prices,
    )


def _fetch_prices(http: httpx.Client, symbol: str, start: date, end: date, interval: str) -> dict[str, Any]:
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86_400
    return _fetch_chart(
        http,
        symbol,
        {
            "period1": str(period1),
            "period2": str(period2),
            "interval": interval,
            "includePrePost": "false",
        },
    )


class YahooQuote:
    name = SOURCE

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def quote(self, symbol: str) -> dict[str, Any]:
        try:
            payload = with_client(self._client, lambda http: _fetch(http, symbol))
        except QuoteLookupError as exc:
            return failed(SOURCE, str(exc))
        return yahoo_quote(payload)

    def prices(self, symbol: str, *, start: date, end: date, interval: str) -> dict[str, Any]:
        try:
            payload = with_client(
                self._client,
                lambda http: _fetch_prices(http, symbol, start, end, interval),
            )
        except QuoteLookupError as exc:
            return failed(SOURCE, str(exc))
        return yahoo_prices(payload)
