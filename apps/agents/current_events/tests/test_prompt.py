from __future__ import annotations

import pytest

from prompt import load_system_prompt, local_system_prompt, system_text

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


def test_local_file_is_the_prompt_the_agent_used_to_inline() -> None:
    text = local_system_prompt()
    assert "collect_current_events" in text
    assert "current-events/date=YYYY-MM-DD/" in text
    assert not text.startswith("\n")


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


def test_load_uses_the_file_when_no_prompt_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BEDROCK_PROMPT_ID", raising=False)
    monkeypatch.delenv("BEDROCK_PROMPT_VERSION", raising=False)
    assert load_system_prompt() == local_system_prompt()


def test_load_pins_the_numbered_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEDROCK_PROMPT_ID", "PROMPT12345")
    monkeypatch.setenv("BEDROCK_PROMPT_VERSION", "2")
    seen: dict[str, str] = {}

    class Client:
        def get_prompt(self, **kwargs: str) -> dict:
            seen.update(kwargs)
            return CHAT_PROMPT

    assert load_system_prompt(Client()) == "Call the tool.\n\nKeep it short."
    assert seen == {"promptIdentifier": "PROMPT12345", "promptVersion": "2"}


def test_load_reports_a_get_prompt_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEDROCK_PROMPT_ID", "PROMPT12345")
    monkeypatch.setenv("BEDROCK_PROMPT_VERSION", "4")

    class Client:
        def get_prompt(self, **kwargs: str) -> dict:
            raise RuntimeError("access denied")

    with pytest.raises(RuntimeError, match="PROMPT12345 version 4"):
        load_system_prompt(Client())


def test_load_omits_the_version_for_the_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEDROCK_PROMPT_ID", "PROMPT12345")
    monkeypatch.delenv("BEDROCK_PROMPT_VERSION", raising=False)
    seen: dict[str, str] = {}

    class Client:
        def get_prompt(self, **kwargs: str) -> dict:
            seen.update(kwargs)
            return CHAT_PROMPT

    load_system_prompt(Client())
    assert seen == {"promptIdentifier": "PROMPT12345"}
