"""What the Federal Reserve can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class FederalReserve(Feed):
    name = "federalreserve"
    _kinds = frozenset({DataKind.RELEASE})
