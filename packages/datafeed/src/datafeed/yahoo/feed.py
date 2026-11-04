"""What Yahoo Finance can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class Yahoo(Feed):
    name = "yahoo"
    _kinds = frozenset({DataKind.HEADLINES, DataKind.QUOTE, DataKind.PRICE_HISTORY})
