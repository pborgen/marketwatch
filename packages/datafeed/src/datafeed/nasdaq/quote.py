"""Nasdaq quote info. No API key.

Last sale, day change, and volume. ``isRealTime`` is the only signal this
source uses to call a print live.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import quote as url_quote

import httpx

from datafeed.http import (
    NASDAQ_HEADERS,
    QuoteLookupError,
    failed,
    request_json,
    round_number,
    row,
    timestamp,
    whole_number,
    with_client,
)

URL = "https://api.nasdaq.com/api/quote/{symbol}/info"
HISTORY_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"
SOURCE = "nasdaq"


def _realtime(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes"}
    return False


def _text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _stat(stats: Any, *needles: str) -> float | None:
    if not isinstance(stats, dict):
        return None
    for key, value in stats.items():
        label = key
        number = value
        if isinstance(value, dict):
            label = str(value.get("label") or key)
            number = value.get("value")
        folded = "".join(ch for ch in label.casefold() if ch.isalnum())
        if any(needle in folded for needle in needles):
            return round_number(number)
    return None


def nasdaq_quote(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    primary = data.get("primaryData") if isinstance(data.get("primaryData"), dict) else {}
    price = round_number(primary.get("lastSalePrice"))
    if price is None:
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        detail = str(status.get("bCodeMessage") or status.get("developerMessage") or "").strip()
        return failed(SOURCE, detail or "No public quote.")
    stats = data.get("keyStats")
    return row(
        SOURCE,
        symbol=_text(data, "symbol"),
        name=_text(data, "companyName"),
        instrument=_text(data, "stockType"),
        price=price,
        currency=_text(primary, "currency"),
        day_change=round_number(primary.get("netChange")),
        day_change_pct=round_number(primary.get("percentageChange")),
        exchange=_text(data, "exchange"),
        volume=whole_number(primary.get("volume")),
        market_cap=whole_number(_stat(stats, "marketcap")),
        pe=_stat(stats, "peratio", "trailingpe"),
        as_of=timestamp(primary.get("lastTradeTimestamp")),
        delayed=not _realtime(primary.get("isRealTime")),
    )


def nasdaq_prices(payload: dict[str, Any]) -> dict[str, Any]:
    """Daily closes from a Nasdaq history payload, oldest first.

    Nasdaq lists the newest session first.
    """
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    table = data.get("tradesTable") if isinstance(data.get("tradesTable"), dict) else {}
    rows = table.get("rows") if isinstance(table.get("rows"), list) else []
    prices: list[dict[str, Any]] = []
    for item in reversed(rows):
        if not isinstance(item, dict):
            continue
        price = round_number(item.get("close"))
        raw_date = str(item.get("date") or "").strip()
        if price is None or not raw_date:
            continue
        try:
            day = datetime.strptime(raw_date, "%m/%d/%Y").date().isoformat()
        except ValueError:
            continue
        prices.append({"date": day, "price": price})
    if not prices:
        return failed(SOURCE, "No price history.")
    return row(SOURCE, symbol=_text(data, "symbol"), prices=prices)


def _fetch_history(http: httpx.Client, symbol: str, start: date, end: date) -> dict[str, Any]:
    bare = url_quote(symbol.split(":")[-1], safe=".")
    span = (end - start).days + 5
    return request_json(
        http,
        "GET",
        HISTORY_URL.format(symbol=bare),
        params={
            "assetclass": "stocks",
            "fromdate": start.isoformat(),
            "todate": end.isoformat(),
            "limit": str(min(max(span, 1), 2000)),
        },
        headers=NASDAQ_HEADERS,
    )


def _fetch(http: httpx.Client, symbol: str) -> dict[str, Any]:
    bare = url_quote(symbol.split(":")[-1], safe=".")
    return request_json(
        http,
        "GET",
        URL.format(symbol=bare),
        params={"assetclass": "stocks"},
        headers=NASDAQ_HEADERS,
    )


class NasdaqQuote:
    name = SOURCE

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def quote(self, symbol: str) -> dict[str, Any]:
        try:
            payload = with_client(self._client, lambda http: _fetch(http, symbol))
        except QuoteLookupError as exc:
            return failed(SOURCE, str(exc))
        return nasdaq_quote(payload)

    def prices(self, symbol: str, *, start: date, end: date) -> dict[str, Any]:
        try:
            payload = with_client(self._client, lambda http: _fetch_history(http, symbol, start, end))
        except QuoteLookupError as exc:
            return failed(SOURCE, str(exc))
        return nasdaq_prices(payload)
