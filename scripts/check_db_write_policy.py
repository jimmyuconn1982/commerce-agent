from __future__ import annotations

"""CLI wrapper for the centralized database write-path policy check."""

import sys
from pathlib import Path

from commerce_agent.db_write_policy import find_write_sql_violations


def main() -> int:
    """Exit non-zero when direct write SQL appears outside `db_write.py`."""
    root = Path(__file__).resolve().parents[1]
    violations = find_write_sql_violations(root)
    if not violations:
        print("db write policy check passed")
        return 0

    print("Direct write SQL is only allowed in src/commerce_agent/db_write.py")
    for path in violations:
        print(path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
