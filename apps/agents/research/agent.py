"""A Strands agent that researches one stock.

The model does not recall prices or filings. It calls tools, then writes a
short brief from what those tools returned. Quotes and history are delayed
Yahoo Finance data. Filings come from SEC EDGAR and need ``SEC_USER_AGENT``
set to a name and email.

Run it from the repo root:

    .venv/bin/python -m pip install -e packages/datafeed -e packages/envfile -e packages/prompt_management -r apps/agents/research/requirements.txt
    .venv/bin/python apps/agents/research/agent.py AAPL
    .venv/bin/python apps/agents/research/agent.py "Compare the last year of MSFT with its latest filings"
    .venv/bin/python apps/agents/research/evaluate.py

Set ``STRANDS_MODEL_ID`` and ``AWS_REGION`` the same way as the demo agent.
A variable already set in the environment wins over ``apps/agents/research/.env``.

The system prompt is stored in Amazon Bedrock Prompt Management.
``system_prompt.txt`` is the text Terraform publishes. ``BEDROCK_PROMPT_ID``
and ``BEDROCK_PROMPT_VERSION`` select a numbered version. Leave both unset
to use the text file.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from datafeed.edgar.filings import EdgarFilings
from datafeed.http import normalize_symbol, rejected
from datafeed.seekingalpha.news import SeekingAlphaRss
from datafeed.yahoo.news import YahooFinanceRss
from datafeed.quotes import QuoteService
from datafeed.yahoo.quote import YahooQuote
from prompt_management.prompt import PROMPT_ID_ENV, PROMPT_VERSION_ENV, load_system_prompt, local_system_prompt
from envfile import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel

load_dotenv(Path(__file__).with_name(".env"))

MODEL_ID = os.environ.get("STRANDS_MODEL_ID", "us.amazon.nova-micro-v1:0")
_SYSTEM_PROMPT = Path(__file__).with_name("system_prompt.txt")


@dataclass
class Feeds:
    """The market-data clients the tools call. Tests swap in a frozen book."""

    quotes: Any = field(default_factory=QuoteService)
    history: Any = field(default_factory=YahooQuote)
    yahoo_news: Any = field(default_factory=YahooFinanceRss)
    seeking_alpha: Any = field(default_factory=SeekingAlphaRss)
    filings: Any = field(default_factory=EdgarFilings)


_FEEDS = Feeds()


@contextmanager
def using_feeds(quotes: Any, yahoo_news: Any, seeking_alpha: Any, filings: Any) -> Any:
    """Point the tools at stand-in feeds for one test or one evaluation case."""
    global _FEEDS
    previous = _FEEDS
    _FEEDS = Feeds(
        quotes=quotes,
        history=quotes,
        yahoo_news=yahoo_news,
        seeking_alpha=seeking_alpha,
        filings=filings,
    )
    try:
        yield
    finally:
        _FEEDS = previous


def _ticker(symbol: str) -> str | None:
    return normalize_symbol(symbol)


def _stories(found: dict[str, Any], source: str) -> list[dict[str, Any]]:
    items = []
    for item in found.get("items") or []:
        if not isinstance(item, dict):
            continue
        story = {
            "title": item.get("title"),
            "published": item.get("published"),
            "link": item.get("link"),
            "source": item.get("source") or source,
        }
        items.append({key: value for key, value in story.items() if value})
    return items


def summarize_prices(prices: list[dict[str, Any]]) -> dict[str, Any]:
    """First close, last close, and the high and low of the series."""
    closes: list[tuple[str, float]] = []
    for item in prices:
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        day = item.get("date")
        if isinstance(price, (int, float)) and isinstance(day, str) and day:
            closes.append((day, float(price)))
    if len(closes) < 2:
        return {}
    first_day, first = closes[0]
    last_day, last = closes[-1]
    values = [price for _day, price in closes]
    change = round(last - first, 4)
    change_pct = round(change / abs(first) * 100, 4) if first else None
    summary: dict[str, Any] = {
        "start": first_day,
        "end": last_day,
        "start_price": first,
        "end_price": last,
        "change": change,
        "high": max(values),
        "low": min(values),
        "sessions": len(closes),
    }
    if change_pct is not None:
        summary["change_pct"] = change_pct
    return summary


@tool
def quote(symbol: str) -> dict[str, Any]:
    """Look up a quote from the first feed that returns a price.

    Nasdaq, TradingView, and Yahoo are tried in that order. A rate limit
    or a miss from one feed tries the next. Yahoo prices are delayed.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    row = _FEEDS.quotes.quote(ticker)
    if row.get("error"):
        return row
    keep = (
        "source",
        "symbol",
        "name",
        "price",
        "currency",
        "previous_close",
        "day_change",
        "day_change_pct",
        "exchange",
        "volume",
        "market_cap",
        "pe",
        "fifty_two_week_high",
        "fifty_two_week_low",
        "market_state",
        "as_of",
        "delayed",
    )
    return {key: row[key] for key in keep if key in row}


@tool
def price_history(symbol: str, months: int = 12) -> dict[str, Any]:
    """Summarize delayed daily closes over a span of months.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
        months: How many months back to measure, from 1 to 24.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    span = max(1, min(int(months), 24))
    end = date.today()
    start = end - timedelta(days=span * 30)
    found = _FEEDS.history.prices(ticker, start=start, end=end, interval="1d")
    if found.get("error"):
        return found
    prices = found.get("prices") if isinstance(found.get("prices"), list) else []
    summary = summarize_prices(prices)
    if not summary:
        return {"symbol": ticker, "error": "No price history."}
    summary["symbol"] = found.get("symbol") or ticker
    summary["currency"] = found.get("currency")
    summary["months"] = span
    summary["delayed"] = True
    return {key: value for key, value in summary.items() if value is not None}


@tool
def headlines(symbol: str, limit: int = 5) -> dict[str, Any]:
    """Fetch recent headlines for one ticker.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
        limit: How many headlines to take from each source, from 1 to 8.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    cap = max(1, min(int(limit), 8))
    items = _stories(_FEEDS.yahoo_news.search(ticker, limit=cap), "yahoo")
    items.extend(_stories(_FEEDS.seeking_alpha.search(ticker, limit=cap), "seekingalpha"))
    return {"symbol": ticker, "count": len(items), "items": items}


@tool
def filings(symbol: str, limit: int = 6) -> dict[str, Any]:
    """List recent SEC filings for one ticker.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
        limit: How many filings to return, from 1 to 12.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    cap = max(1, min(int(limit), 12))
    client = _FEEDS.filings if _FEEDS.filings is not None else EdgarFilings()
    found = client.filings(ticker, limit=cap)
    if found.get("error"):
        return {"symbol": ticker, "error": found["error"]}
    items = []
    for item in found.get("items") or []:
        if not isinstance(item, dict):
            continue
        filing = {
            "form": item.get("form"),
            "filed": item.get("filed"),
            "description": item.get("description"),
            "link": item.get("link"),
        }
        items.append({key: value for key, value in filing.items() if value})
    return {"symbol": ticker, "count": len(items), "items": items}


def _prompt_text() -> str:
    prompt_id = os.environ.get(PROMPT_ID_ENV, "").strip()
    if not prompt_id:
        return local_system_prompt(_SYSTEM_PROMPT)
    return load_system_prompt(prompt_id, os.environ.get(PROMPT_VERSION_ENV, ""))


def build_agent() -> Agent:
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    model = BedrockModel(
        model_id=MODEL_ID,
        temperature=0.2,
        streaming=False,
        region_name=region,
    )
    return Agent(
        model=model,
        system_prompt=_prompt_text(),
        tools=[quote, price_history, headlines, filings],
        callback_handler=None,
        name="stock-research",
    )


def answer_text(result: Any) -> str:
    parts: list[str] = []
    for block in result.message["content"]:
        text = block.get("text")
        if text and text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def _preview(block: dict[str, Any]) -> str:
    result = block["toolResult"]
    chunks: list[str] = []
    for item in result.get("content") or []:
        if item.get("text"):
            chunks.append(str(item["text"]))
        elif "json" in item:
            chunks.append(json.dumps(item["json"], default=str))
    text = " ".join(chunks)
    if len(text) > 160:
        text = text[:157] + "..."
    return f"{result['status']}: {text}" if text else result["status"]


def print_turn(agent: Agent, start: int, result: Any) -> None:
    results: dict[str, dict[str, Any]] = {}
    for message in agent.messages[start:]:
        for block in message["content"]:
            if "toolResult" in block:
                results[block["toolResult"]["toolUseId"]] = block

    print(f"\nloop: {result.metrics.cycle_count} model call(s), stop={result.stop_reason}")
    for message in agent.messages[start:]:
        for block in message["content"]:
            if "toolUse" not in block:
                continue
            use = block["toolUse"]
            print(f"  model called {use['name']} {json.dumps(use['input'], default=str)}")
            returned = results.get(use["toolUseId"])
            if returned is not None:
                print(f"  tool returned {_preview(returned)}")
    print()
    print(answer_text(result) or "(The model returned no text.)")
    print()


def ask(agent: Agent, prompt: str) -> None:
    start = len(agent.messages)
    try:
        result = agent(prompt)
    except Exception as exc:
        print(f"\nThe model call failed: {exc}")
        print("Check the AWS credentials this process is using, the region, and")
        print(f"that the account can invoke {MODEL_ID}.")
        print()
        return
    print_turn(agent, start, result)


def _prompt(argv: list[str]) -> str:
    text = " ".join(argv).strip()
    if normalize_symbol(text):
        return f"Research {text}."
    return text


def _banner(agent: Agent) -> None:
    model_id = agent.model.config["model_id"]
    region = agent.model.client.meta.region_name
    print("Strands stock research")
    print(f"model: {model_id}  region: {region}")
    print("Give a ticker. The agent quotes it, checks the past year, headlines, and filings.")
    print("Commands: /quit")
    print()


def repl(agent: Agent) -> None:
    _banner(agent)
    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt:
            continue
        if prompt in {"/quit", "/exit"}:
            return
        ask(agent, _prompt([prompt]))


def main(argv: list[str]) -> None:
    agent = build_agent()
    if argv:
        _banner(agent)
        ask(agent, _prompt(argv))
        return
    repl(agent)


if __name__ == "__main__":
    main(sys.argv[1:])
