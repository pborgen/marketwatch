"""The research cases. A handful of real prompts, each with a tool trajectory.

Add a case when a live run fails in a way these do not already cover.
"""

from __future__ import annotations

from dataclasses import dataclass

from strands_evals import Case

_TOOLS = ("quote", "price_history", "headlines", "filings")


@dataclass(frozen=True)
class ResearchCase:
    name: str
    prompt: str
    book: str
    tools: tuple[str, ...]
    symbols: tuple[str, ...]
    mention: tuple[str, ...] = ()
    refuse: bool = False

    def metadata(self) -> dict[str, object]:
        return {
            "book": self.book,
            "tools": list(self.tools),
            "symbols": list(self.symbols),
            "mention": list(self.mention),
            "refuse": self.refuse,
        }


CASES: tuple[ResearchCase, ...] = (
    ResearchCase(
        name="one ticker",
        prompt="Research AAPL.",
        book="aapl",
        tools=_TOOLS,
        symbols=("AAPL",),
        mention=("delayed",),
    ),
    ResearchCase(
        name="two tickers",
        prompt="Compare the last year of MSFT with AAPL.",
        book="compare",
        tools=_TOOLS,
        symbols=("AAPL", "MSFT"),
        mention=("delayed",),
    ),
    ResearchCase(
        name="filing error",
        prompt="Research AAPL.",
        book="filings-down",
        tools=_TOOLS,
        symbols=("AAPL",),
        mention=("delayed", "SEC_USER_AGENT"),
    ),
    ResearchCase(
        name="unknown ticker",
        prompt="Research ZZZZ.",
        book="empty",
        tools=_TOOLS,
        symbols=("ZZZZ",),
        mention=("ZZZZ",),
    ),
    ResearchCase(
        name="no ticker",
        prompt="What should I buy this week?",
        book="empty",
        tools=(),
        symbols=(),
        refuse=True,
    ),
)


def strands_cases() -> list[Case]:
    return [Case(name=spec.name, input=spec.prompt, metadata=spec.metadata()) for spec in CASES]
