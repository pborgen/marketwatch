"""A small Strands agent you can talk to.

Strands is a loop around a model. You give the agent a model, a system prompt,
and tools. Each time you call ``agent(prompt)`` the SDK does this:

1. Send the conversation and the tool list to the model.
2. If the model asks for a tool, run that function and send the result back.
3. Repeat until the model writes an answer.

You do not write that loop. You write the tools and read what the model did.

Run it from the repo root:

    .venv/bin/python -m pip install -e packages/datafeed 'strands-agents>=1.0'
    .venv/bin/python apps/agents/demo/agent.py
    .venv/bin/python apps/agents/demo/agent.py "Quote AAPL and save it to my watchlist"

The model is Amazon Bedrock. The process uses your normal AWS credentials
(``aws configure``, a profile, or environment variables). The account needs
``bedrock:InvokeModel`` on the model below. Set the model in
``apps/agents/demo/.env`` as ``STRANDS_MODEL_ID``. A variable already set in
the environment wins. Set the region with ``AWS_REGION``.

Docs: https://strandsagents.com/docs/user-guide/sdk/quickstart/python/
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from datafeed.http import normalize_symbol, rejected
from datafeed.yahoo.news import YahooFinanceRss
from datafeed.yahoo.quote import YahooQuote
from strands import Agent, ToolContext, tool
from strands.models import BedrockModel


def _load_dotenv(path: Path) -> None:
    """Read KEY=value lines. Variables already set in the environment stay."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(Path(__file__).with_name(".env"))

# Nova Micro is the cheapest Bedrock model that can call tools. It has no
# global inference profile, so the fallback is the US geo profile.
MODEL_ID = os.environ.get("STRANDS_MODEL_ID", "us.amazon.nova-micro-v1:0")
WATCHLIST = "watchlist"
_QUOTES = YahooQuote()
_NEWS = YahooFinanceRss()

SYSTEM_PROMPT = """
You are a market-watch assistant. A person is using you to learn how a
Strands agent works, so call tools instead of answering from memory.

Use quote for prices and headlines for news. Those figures come from delayed
Yahoo Finance data. Say that the price is delayed. If a tool returns an error,
report the error.

The watchlist is agent state, kept outside the conversation. Read and change
it only with the watchlist tools.

Keep the reply to a few sentences.
""".strip()


def _watchlist(tool_context: ToolContext) -> list[str]:
    saved = tool_context.agent.state.get(WATCHLIST) or []
    return [str(symbol) for symbol in saved]


def _ticker(symbol: str) -> str | None:
    return normalize_symbol(symbol)


@tool
def quote(symbol: str) -> dict[str, Any]:
    """Look up a delayed quote.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    row = _QUOTES.quote(ticker)
    if row.get("error"):
        return row
    keep = (
        "symbol",
        "name",
        "price",
        "currency",
        "previous_close",
        "day_change",
        "day_change_pct",
        "exchange",
        "market_state",
        "as_of",
        "delayed",
    )
    return {key: row[key] for key in keep if key in row}


@tool
def headlines(symbol: str, limit: int = 5) -> dict[str, Any]:
    """Fetch recent headlines for one ticker.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
        limit: How many headlines to return, from 1 to 8.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    cap = max(1, min(int(limit), 8))
    found = _NEWS.search(ticker, limit=cap)
    items = []
    for item in found.get("items") or []:
        items.append(
            {
                "title": item.get("title"),
                "published": item.get("published"),
                "link": item.get("link"),
            }
        )
    payload: dict[str, Any] = {"symbol": ticker, "count": len(items), "items": items}
    if found.get("error"):
        payload["error"] = found["error"]
    return payload


@tool(context=True)
def add_to_watchlist(symbol: str, tool_context: ToolContext) -> dict[str, Any]:
    """Remember a ticker for later questions in this session.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    symbols = _watchlist(tool_context)
    if ticker not in symbols:
        symbols.append(ticker)
        tool_context.agent.state.set(WATCHLIST, symbols)
    return {"added": ticker, "watchlist": symbols}


@tool(context=True)
def remove_from_watchlist(symbol: str, tool_context: ToolContext) -> dict[str, Any]:
    """Drop a ticker from the watchlist.

    Args:
        symbol: Ticker such as AAPL or NASDAQ:AAPL.
    """
    ticker = _ticker(symbol)
    if ticker is None:
        return rejected(symbol)
    symbols = [item for item in _watchlist(tool_context) if item != ticker]
    tool_context.agent.state.set(WATCHLIST, symbols)
    return {"removed": ticker, "watchlist": symbols}


@tool(context=True)
def show_watchlist(tool_context: ToolContext) -> dict[str, Any]:
    """Return the tickers saved on the watchlist."""
    return {"watchlist": _watchlist(tool_context)}


def build_agent() -> Agent:
    """One agent keeps its conversation and its state until the process exits."""
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    model = BedrockModel(
        model_id=MODEL_ID,
        temperature=0.2,
        streaming=False,
        **({"region_name": region} if region else {}),
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[quote, headlines, add_to_watchlist, remove_from_watchlist, show_watchlist],
        state={WATCHLIST: []},
        # The default handler prints tokens as they stream. This demo prints
        # the finished turn itself so the tool loop is easy to read.
        callback_handler=None,
        name="market-watch",
    )


def _answer(result: Any) -> str:
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
    """Show the steps the model took, then its answer.

    ``agent.messages`` is the conversation. Tool requests and tool results are
    messages, the same as what you typed.
    """
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
    print(_answer(result) or "(The model returned no text.)")
    print()


def ask(agent: Agent, prompt: str) -> None:
    start = len(agent.messages)
    try:
        result = agent(prompt)
    except Exception as exc:
        print(f"\nThe model call failed: {exc}")
        print("Check the AWS credentials this process is using, the region, and")
        print(f"that the account can invoke {MODEL_ID}.")
        print("https://strandsagents.com/docs/user-guide/sdk/model-providers/amazon-bedrock/")
        print()
        return
    print_turn(agent, start, result)


def _banner(agent: Agent) -> None:
    model_id = agent.model.config["model_id"]
    region = agent.model.client.meta.region_name
    print("Strands market-watch demo")
    print(f"model: {model_id}  region: {region}")
    print("The same agent object remembers the conversation and the watchlist.")
    print("Try: Quote AAPL, then add it and MSFT to my watchlist.")
    print("Commands: /state  /quit")
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
        if prompt == "/state":
            print(json.dumps(agent.state.get(), indent=2))
            print()
            continue
        ask(agent, prompt)


def main(argv: list[str]) -> None:
    agent = build_agent()
    if argv:
        _banner(agent)
        ask(agent, " ".join(argv))
        return
    repl(agent)


if __name__ == "__main__":
    main(sys.argv[1:])
