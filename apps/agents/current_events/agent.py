"""A Strands agent that collects current events into S3.

The model does not write the documents. It calls ``collect_current_events``,
and that tool fetches headlines and official releases, shapes each one into
an OpenSearch document, and stores newline-delimited JSON under today's UTC
date.

Run it from the repo root:

    .venv/bin/python -m pip install -e packages/datafeed -e packages/envfile -r apps/agents/current_events/requirements.txt
    DATA_BUCKET=your-bucket .venv/bin/python apps/agents/current_events/agent.py
    DATA_BUCKET=your-bucket .venv/bin/python apps/agents/current_events/agent.py "Collect today's events on oil prices"

``DATA_BUCKET`` is the application bucket. ``serve.py`` is the same agent
on the AgentCore HTTP contract. Set ``STRANDS_MODEL_ID`` and ``AWS_REGION``
the same way as the demo agent. A variable already set in the environment
wins over ``apps/agents/current_events/.env``.

The system prompt is stored in Amazon Bedrock Prompt Management.
``system_prompt.txt`` is the text Terraform publishes. The runtime sets
``BEDROCK_PROMPT_ID`` and ``BEDROCK_PROMPT_VERSION`` to a numbered version,
and this process loads that version. Leave both unset to use the text file.

To store without a model call, run ``collect.py``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from envfile import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel

from collect import run_collection
from prompt import PROMPT_ID_ENV, PROMPT_VERSION_ENV, load_system_prompt

load_dotenv(Path(__file__).with_name(".env"))

MODEL_ID = os.environ.get("STRANDS_MODEL_ID", "us.amazon.nova-micro-v1:0")


@tool
def collect_current_events(topics: str = "", limit: int = 8, include_releases: bool = True) -> dict[str, Any]:
    """Collect current events and store them in S3 as OpenSearch documents.

    Each stored line is one document. The text field is the RAG passage.
    The id field is the OpenSearch document id. The object key includes
    the UTC date of this run.

    Args:
        topics: Comma-separated subjects. Blank uses the default market topics.
        limit: Headlines to keep from each feed for each topic, from 1 to 20.
        include_releases: Also store the latest Federal Reserve and BLS releases.
    """
    return run_collection(topics, limit, include_releases=include_releases)


def build_agent() -> Agent:
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    model = BedrockModel(
        model_id=MODEL_ID,
        temperature=0.2,
        streaming=False,
        **({"region_name": region} if region else {}),
    )
    return Agent(
        model=model,
        system_prompt=load_system_prompt(),
        tools=[collect_current_events],
        callback_handler=None,
        name="current-events",
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
    if len(text) > 180:
        text = text[:177] + "..."
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


def _banner(agent: Agent) -> None:
    model_id = agent.model.config["model_id"]
    region = agent.model.client.meta.region_name
    bucket = os.environ.get("DATA_BUCKET", "(DATA_BUCKET is not set)")
    print("Current-events agent")
    print(f"model: {model_id}  region: {region}")
    print(f"bucket: {bucket}")
    print(f"prompt: {_prompt_label()}")
    print("Objects land at current-events/date=YYYY-MM-DD/ as newline-delimited JSON.")
    print("Try: Collect today's events.")
    print("Commands: /quit")
    print()


def _prompt_label() -> str:
    prompt_id = os.environ.get(PROMPT_ID_ENV, "").strip()
    if not prompt_id:
        return "system_prompt.txt"
    version = os.environ.get(PROMPT_VERSION_ENV, "").strip() or "DRAFT"
    return f"{prompt_id} version {version}"


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
