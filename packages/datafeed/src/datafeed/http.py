"""HTTP helpers shared by the data feeds. Each source owns its URL and field mapping."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from datafeed.parse import as_float

TICKER_ERROR = "Ticker must look like AAPL or NASDAQ:AAPL."
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
TV_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}
NASDAQ_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}
_TICKER_RE = re.compile(r"^(?:[A-Z][A-Z0-9]{0,11}:)?[A-Z0-9][A-Z0-9.\-]{0,14}$")
_SCALES = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
_BLANK = {"N/A", "NA", "--", "NM"}


class QuoteLookupError(Exception):
    """A quote source failed before it had a payload to parse."""


def normalize_symbol(raw: str) -> str | None:
    """``AAPL`` or ``NASDAQ:AAPL``. ``None`` when the text is not a ticker."""
    ticker = " ".join((raw or "").split()).upper()
    if not _TICKER_RE.fullmatch(ticker):
        return None
    return ticker


def rejected(symbol: str) -> dict[str, Any]:
    shown = " ".join((symbol or "").split())[:40]
    return {"ticker": shown, "error": TICKER_ERROR}


def failed(source: str, message: str) -> dict[str, Any]:
    return {"source": source, "error": message}


def row(source: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"source": source}
    for key, value in fields.items():
        if value is None or value == "":
            continue
        payload[key] = value
    return payload


def money(value: Any) -> float | None:
    """Parse a price, percent, or scaled figure such as ``$1.2T`` or ``-0.20%``."""
    if isinstance(value, dict):
        if "value" in value:
            return money(value.get("value"))
        return as_float(value)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "").replace("+", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1].strip()
        if not cleaned or cleaned.upper() in _BLANK:
            return None
        if cleaned.upper() == "UNCH":
            return 0.0
        scale = _SCALES.get(cleaned[-1].upper())
        if scale is not None and len(cleaned) > 1:
            number = as_float(cleaned[:-1])
            if number is None:
                return None
            return number * scale
        return as_float(cleaned)
    return as_float(value)


def round_number(value: Any) -> float | None:
    number = money(value)
    if number is None:
        return None
    return round(number, 4)


def whole_number(value: Any) -> int | None:
    """Share counts and market cap. Drops the fraction Nasdaq puts on a live volume."""
    number = money(value)
    if number is None:
        return None
    return int(round(number))


def timestamp(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    number = as_float(value)
    if number is None:
        return None
    try:
        moment = datetime.fromtimestamp(number, timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def request_json(http: httpx.Client, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = http.request(method, url, **kwargs)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise QuoteLookupError(f"HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise QuoteLookupError("network error") from exc
    except ValueError as exc:
        raise QuoteLookupError("response was not JSON") from exc
    if not isinstance(payload, dict):
        raise QuoteLookupError("response was not an object")
    return payload


def with_client(client: httpx.Client | None, fn: Any) -> Any:
    if client is not None:
        return fn(client)
    with httpx.Client(timeout=8.0, follow_redirects=True, headers=HEADERS) as http:
        return fn(http)
