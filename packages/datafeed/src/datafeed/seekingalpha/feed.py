"""What Seeking Alpha can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class SeekingAlpha(Feed):
    name = "seekingalpha"
    _kinds = frozenset({DataKind.HEADLINES})
