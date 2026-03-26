from __future__ import annotations

"""Checks that application-side write SQL stays behind the shared writer.

Inputs:
- a source tree root

Outputs:
- a list of source files that contain direct write SQL outside the allowed module

Role:
- keep database mutations centralized in `db_write.py`
- support local checks and CI enforcement

Upgrade path:
- extend the allowlist when new shared writer modules are introduced
- tighten the regex or AST-based detection if write patterns become more complex
"""

from pathlib import Path
import re

WRITE_SQL_PATTERN = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|TRUNCATE\s+TABLE)\b",
    re.IGNORECASE,
)

ALLOWED_WRITE_FILES = {
    Path("src/commerce_agent/db_write.py"),
}


def find_write_sql_violations(root: Path) -> list[Path]:
    """Return source files that contain direct write SQL outside the allowlist."""
    violations: list[Path] = []
    for path in sorted((root / "src" / "commerce_agent").rglob("*.py")):
        relative = path.relative_to(root)
        if relative in ALLOWED_WRITE_FILES:
            continue
        if WRITE_SQL_PATTERN.search(path.read_text(encoding="utf-8")):
            violations.append(relative)
    return violations
