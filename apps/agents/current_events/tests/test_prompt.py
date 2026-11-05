from __future__ import annotations

from pathlib import Path

from prompt_management.prompt import local_system_prompt

_TEXT = Path(__file__).resolve().parents[1] / "system_prompt.txt"


def test_local_file_is_the_prompt_the_agent_used_to_inline() -> None:
    text = local_system_prompt(_TEXT)
    assert "collect_current_events" in text
    assert "current-events/date=YYYY-MM-DD/" in text
    assert not text.startswith("\n")
