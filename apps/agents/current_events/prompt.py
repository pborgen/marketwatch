"""Load the current-events system prompt.

Terraform publishes ``system_prompt.txt`` with Amazon Bedrock Prompt
Management and sets ``BEDROCK_PROMPT_ID`` and ``BEDROCK_PROMPT_VERSION`` on
the runtime. Those variables select a numbered version. Prompt management
keeps that version immutable, so a draft edit does not change a running
agent until a new version is published.

Leave both variables unset to read ``system_prompt.txt``. That is the local
path, before the prompt exists in the account.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PROMPT_ID_ENV = "BEDROCK_PROMPT_ID"
PROMPT_VERSION_ENV = "BEDROCK_PROMPT_VERSION"
_TEXT_FILE = Path(__file__).with_name("system_prompt.txt")


def local_system_prompt() -> str:
    if not _TEXT_FILE.is_file():
        raise RuntimeError(
            f"{PROMPT_ID_ENV} is not set, and {_TEXT_FILE.name} is not next to the agent."
        )
    text = _TEXT_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{_TEXT_FILE.name} is empty.")
    return text


def system_text(prompt: dict[str, Any]) -> str:
    """System text from a GetPrompt response.

    A chat prompt stores it on the system blocks. A text prompt stores it on
    the text template. The console test message is ignored.
    """
    variants = prompt.get("variants") or []
    if not isinstance(variants, list):
        variants = []
    name = prompt.get("defaultVariant")
    variant = next((item for item in variants if isinstance(item, dict) and item.get("name") == name), None)
    if variant is None:
        variant = next((item for item in variants if isinstance(item, dict)), None)
    if variant is None:
        raise RuntimeError("The Bedrock prompt has no variants.")
    text = _variant_text(variant)
    if text:
        return text
    label = variant.get("name") or "default"
    raise RuntimeError(f"Bedrock prompt variant {label} has no system text.")


def load_system_prompt(client: Any | None = None) -> str:
    prompt_id = os.environ.get(PROMPT_ID_ENV, "").strip()
    if not prompt_id:
        return local_system_prompt()
    version = os.environ.get(PROMPT_VERSION_ENV, "").strip()
    where = f"{prompt_id} version {version}" if version else f"{prompt_id} draft"
    kwargs: dict[str, str] = {"promptIdentifier": prompt_id}
    if version:
        kwargs["promptVersion"] = version
    agent = client or _bedrock_agent()
    try:
        prompt = agent.get_prompt(**kwargs)
    except Exception as exc:
        raise RuntimeError(f"Could not load the Bedrock system prompt {where}: {exc}") from exc
    try:
        return system_text(prompt)
    except RuntimeError as exc:
        raise RuntimeError(f"Could not read the Bedrock system prompt {where}: {exc}") from exc


def _variant_text(variant: dict[str, Any]) -> str:
    template = variant.get("templateConfiguration") or {}
    if not isinstance(template, dict):
        return ""
    chat = template.get("chat") or {}
    parts: list[str] = []
    if isinstance(chat, dict):
        for block in chat.get("system") or []:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    if parts:
        return "\n\n".join(parts)
    text_template = template.get("text") or {}
    text = text_template.get("text") if isinstance(text_template, dict) else None
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


def _bedrock_agent() -> Any:
    import boto3

    return boto3.client("bedrock-agent")
