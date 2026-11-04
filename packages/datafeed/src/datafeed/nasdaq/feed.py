"""What Nasdaq can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class Nasdaq(Feed):
    name = "nasdaq"
    _kinds = frozenset({DataKind.HEADLINES, DataKind.QUOTE, DataKind.PRICE_HISTORY})
