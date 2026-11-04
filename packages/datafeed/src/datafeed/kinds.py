"""Kinds of data a feed can return.

Feeds that list the same kind can be aggregated. Ask a feed with ``kinds``,
or ask ``feeds_for`` which feeds supply one kind.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar


class DataKind(StrEnum):
    """One kind of payload. The same kind has the same role on every feed."""

    HEADLINES = "headlines"
    QUOTE = "quote"
    PRICE_HISTORY = "price_history"
    SCREEN = "screen"
    FILING = "filing"
    RELEASE = "release"


class Feed:
    """A vendor. ``kinds`` is what that vendor can fetch."""

    name: ClassVar[str]
    _kinds: ClassVar[frozenset[DataKind]] = frozenset()

    @classmethod
    def kinds(cls) -> frozenset[DataKind]:
        return cls._kinds


def all_feeds() -> tuple[type[Feed], ...]:
    """Every feed. Imported here so a feed module can import ``DataKind``."""
    from datafeed.bing.feed import Bing
    from datafeed.bls.feed import Bls
    from datafeed.edgar.feed import Edgar
    from datafeed.federalreserve.feed import FederalReserve
    from datafeed.google.feed import Google
    from datafeed.nasdaq.feed import Nasdaq
    from datafeed.seekingalpha.feed import SeekingAlpha
    from datafeed.tradingview.feed import TradingView
    from datafeed.yahoo.feed import Yahoo

    return (Bing, Bls, Edgar, FederalReserve, Google, Nasdaq, SeekingAlpha, TradingView, Yahoo)


def feeds_for(kind: DataKind) -> list[type[Feed]]:
    """Feeds that can return ``kind``, in ``all_feeds`` order."""
    return [feed for feed in all_feeds() if kind in feed.kinds()]
