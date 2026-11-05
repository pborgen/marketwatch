from __future__ import annotations

from pathlib import Path

import pytest

from prompt_management.prompt import load_system_prompt, local_system_prompt, system_text

CHAT_PROMPT = {
    "defaultVariant": "system",
    "version": "2",
    "variants": [
        {
            "name": "system",
            "templateType": "CHAT",
            "templateConfiguration": {
                "chat": {
                    "system": [{"text": "  Call the tool.  "}, {"text": "Keep it short."}],
                    "messages": [{"role": "user", "content": [{"text": "Collect today's events."}]}],
                }
            },
        }
    ],
}


def test_local_file_is_stripped(tmp_path: Path) -> None:
    path = tmp_path / "system_prompt.txt"
    path.write_text("\n  Call the tool.  \n")
    assert local_system_prompt(path) == "Call the tool."


def test_missing_file_names_the_env_var(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="BEDROCK_PROMPT_ID"):
        local_system_prompt(tmp_path / "system_prompt.txt")


def test_system_text_joins_chat_system_blocks() -> None:
    assert system_text(CHAT_PROMPT) == "Call the tool.\n\nKeep it short."


def test_system_text_reads_a_text_template() -> None:
    prompt = {
        "defaultVariant": "system",
        "variants": [
            {
                "name": "system",
                "templateType": "TEXT",
                "templateConfiguration": {"text": {"text": "  Use the tool.  "}},
            }
        ],
    }
    assert system_text(prompt) == "Use the tool."


def test_system_text_rejects_a_prompt_with_no_system_text() -> None:
    prompt = {
        "defaultVariant": "system",
        "variants": [
            {
                "name": "system",
                "templateConfiguration": {"chat": {"messages": [{"role": "user", "content": [{"text": "Hi"}]}]}},
            }
        ],
    }
    with pytest.raises(RuntimeError, match="no system text"):
        system_text(prompt)


def test_load_rejects_a_blank_id() -> None:
    with pytest.raises(RuntimeError, match="prompt id"):
        load_system_prompt("  ")


def test_load_pins_the_numbered_version() -> None:
    seen: dict[str, str] = {}

    class Client:
        def get_prompt(self, **kwargs: str) -> dict:
            seen.update(kwargs)
            return CHAT_PROMPT

    assert load_system_prompt("PROMPT12345", "2", Client()) == "Call the tool.\n\nKeep it short."
    assert seen == {"promptIdentifier": "PROMPT12345", "promptVersion": "2"}


def test_load_reports_a_get_prompt_failure() -> None:
    class Client:
        def get_prompt(self, **kwargs: str) -> dict:
            raise RuntimeError("access denied")

    with pytest.raises(RuntimeError, match="PROMPT12345 version 4"):
        load_system_prompt("PROMPT12345", "4", Client())


def test_load_omits_the_version_for_the_draft() -> None:
    seen: dict[str, str] = {}

    class Client:
        def get_prompt(self, **kwargs: str) -> dict:
            seen.update(kwargs)
            return CHAT_PROMPT

    load_system_prompt("PROMPT12345", "", Client())
    assert seen == {"promptIdentifier": "PROMPT12345"}
