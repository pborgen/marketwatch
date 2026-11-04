"""What EDGAR can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class Edgar(Feed):
    name = "edgar"
    _kinds = frozenset({DataKind.FILING})
