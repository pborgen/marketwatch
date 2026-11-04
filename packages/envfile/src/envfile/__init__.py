"""Load KEY=value files into the process environment.

A variable already set in the environment stays. A missing file is ignored.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | str) -> None:
    """Read KEY=value lines. Variables already set in the environment stay."""
    file = Path(path)
    if not file.is_file():
        return
    for raw in file.read_text().splitlines():
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
