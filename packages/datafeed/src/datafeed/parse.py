"""Small parsers the feeds need. Portfolio parsing stays in the invest repo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Quote:
    symbol: str
    name: str | None = None
    close: float | None = None
    change_pct: float | None = None
    change_abs: float | None = None
    recommend: float | None = None
    rating: str | None = None
    sector: str | None = None
    industry: str | None = None
    volume: float | None = None
    market_cap: float | None = None
    pe: float | None = None
    update_mode: str | None = None


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        if "v" in value:
            return as_float(value.get("v"))
        if "value" in value:
            return as_float(value.get("value"))
        if "user" in value:
            return as_float(value.get("user"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def recommend_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.5:
        return "Strong buy"
    if score >= 0.1:
        return "Buy"
    if score > -0.1:
        return "Neutral"
    if score > -0.5:
        return "Sell"
    return "Strong sell"


def parse_quotes(payload: Any, columns: list[str]) -> dict[str, Quote]:
    data = payload if isinstance(payload, dict) else {}
    rows = data.get("data") if isinstance(data.get("data"), list) else []
    quotes: dict[str, Quote] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = as_str(row.get("s"))
        values = row.get("d") if isinstance(row.get("d"), list) else []
        if not symbol:
            continue
        mapped = {columns[i]: values[i] if i < len(values) else None for i in range(len(columns))}
        score = as_float(mapped.get("Recommend.All"))
        quotes[symbol] = Quote(
            symbol=symbol,
            name=as_str(mapped.get("description") or mapped.get("name")),
            close=as_float(mapped.get("close")),
            change_pct=as_float(mapped.get("change")),
            change_abs=as_float(mapped.get("change_abs")),
            recommend=score,
            rating=recommend_label(score),
            sector=as_str(mapped.get("sector")),
            industry=as_str(mapped.get("industry")),
            volume=as_float(mapped.get("volume")),
            market_cap=as_float(mapped.get("market_cap_basic")),
            pe=as_float(mapped.get("price_earnings_ttm")),
            update_mode=as_str(mapped.get("update_mode")),
        )
    return quotes
