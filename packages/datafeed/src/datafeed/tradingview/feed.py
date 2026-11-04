"""What the TradingView public scanner can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class TradingView(Feed):
    name = "tradingview"
    _kinds = frozenset({DataKind.QUOTE, DataKind.SCREEN})
