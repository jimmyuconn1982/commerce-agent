from pathlib import Path

from commerce_agent.db_write_policy import ALLOWED_WRITE_FILES, find_write_sql_violations


def test_db_write_policy_has_no_current_violations() -> None:
    root = Path(__file__).resolve().parents[1]
    assert find_write_sql_violations(root) == []


def test_db_write_policy_allowlist_only_contains_shared_writer() -> None:
    assert ALLOWED_WRITE_FILES == {Path("src/commerce_agent/db_write.py")}
