"""What Bing can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class Bing(Feed):
    name = "bing"
    _kinds = frozenset({DataKind.HEADLINES})
