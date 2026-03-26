from __future__ import annotations

"""Lightweight .env loading for local development.

Inputs:
- project-root `.env` file with KEY=VALUE lines

Outputs:
- environment variables populated into `os.environ` when missing

Role:
- support local development without requiring manual `export`
- keep secret loading outside the main application logic

Upgrade path:
- replace with python-dotenv or pydantic-settings later if needed
"""

import os
from pathlib import Path


def load_dotenv(dotenv_path: Path | None = None) -> None:
    """Load a local .env file into the current process if present."""
    path = dotenv_path or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
