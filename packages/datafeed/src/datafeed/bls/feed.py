"""What the Bureau of Labor Statistics can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class Bls(Feed):
    name = "bls"
    _kinds = frozenset({DataKind.RELEASE})
