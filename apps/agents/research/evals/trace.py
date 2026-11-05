"""Tool calls the agent actually made, read back from its messages."""

from __future__ import annotations

from typing import Any

from datafeed.http import normalize_symbol


def bare_ticker(symbol: str) -> str | None:
    """``NASDAQ:AAPL`` and ``aapl`` both become ``AAPL``. Anything else is ``None``."""
    ticker = normalize_symbol(symbol)
    if ticker is None:
        return None
    return ticker.split(":")[-1]


def tool_calls(messages: list[Any]) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if not isinstance(block, dict) or "toolUse" not in block:
                continue
            use = block["toolUse"]
            raw = (use.get("input") or {}).get("symbol", "")
            calls.append({"name": str(use.get("name") or ""), "symbol": str(raw)})
    return calls
