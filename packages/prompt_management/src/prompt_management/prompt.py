"""Load a system prompt from Amazon Bedrock Prompt Management.

``load_system_prompt`` takes a prompt id and a version and calls GetPrompt.
A numbered version is immutable. Pass an empty version to read the draft.

``local_system_prompt`` reads a ``system_prompt.txt`` when the process has
no prompt id yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROMPT_ID_ENV = "BEDROCK_PROMPT_ID"
PROMPT_VERSION_ENV = "BEDROCK_PROMPT_VERSION"


def local_system_prompt(path: Path | str) -> str:
    """Read one ``system_prompt.txt``. Blank files are rejected."""
    file = Path(path)
    if not file.is_file():
        raise RuntimeError(f"{PROMPT_ID_ENV} is not set, and {file.name} is missing.")
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{file.name} is empty.")
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
    variant = next(
        (item for item in variants if isinstance(item, dict) and item.get("name") == name),
        None,
    )
    if variant is None:
        variant = next((item for item in variants if isinstance(item, dict)), None)
    if variant is None:
        raise RuntimeError("The Bedrock prompt has no variants.")
    text = _variant_text(variant)
    if text:
        return text
    label = variant.get("name") or "default"
    raise RuntimeError(f"Bedrock prompt variant {label} has no system text.")


def load_system_prompt(prompt_id: str, version: str = "", client: Any | None = None) -> str:
    """Load the system text for one Bedrock prompt id and version.

    ``version`` is the published number, such as ``"2"``. An empty version
    reads the draft.
    """
    prompt_id = prompt_id.strip()
    version = version.strip()
    if not prompt_id:
        raise RuntimeError("A Bedrock prompt id is required.")
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
