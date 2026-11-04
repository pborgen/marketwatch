"""What Google News can return."""

from __future__ import annotations

from datafeed.kinds import DataKind, Feed


class Google(Feed):
    name = "google"
    _kinds = frozenset({DataKind.HEADLINES})
