from __future__ import annotations

import os
from pathlib import Path

from envfile import load_dotenv


def test_missing_file_is_ignored(tmp_path: Path) -> None:
    load_dotenv(tmp_path / "missing.env")


def test_loads_assignments_and_leaves_existing_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KEEP", "already")
    monkeypatch.delenv("NEW", raising=False)
    monkeypatch.delenv("EXPORTED", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            [
                "# comment",
                "",
                "not a pair",
                "KEEP=from-file",
                "NEW=from-file",
                "export EXPORTED=yes",
                "QUOTED=\"hello\"",
                "=novalue",
            ]
        )
    )

    load_dotenv(path)

    assert os.environ["KEEP"] == "already"
    assert os.environ["NEW"] == "from-file"
    assert os.environ["EXPORTED"] == "yes"
    assert os.environ["QUOTED"] == "hello"
    assert "" not in os.environ
