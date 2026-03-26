from __future__ import annotations

"""Deployment setup utilities for demo environments.

Inputs:
- a target PostgreSQL `DATABASE_URL`
- checked-in SQL migration files
- public seed source configuration

Outputs:
- initialized database schema
- loaded public demo seed data
- built semantic indexes

Role:
- provide one repeatable setup command for platforms like Render
- avoid manual migration/seed/index steps during demo deployment

Upgrade path:
- replace raw SQL file execution with a dedicated migration runner later
- add incremental seed/index refresh commands for production environments
"""

import os
from pathlib import Path

import psycopg

from .embeddings import build_semantic_indexes, semantic_index_status
from .seed_data import (
    DEFAULT_DATABASE_URL,
    DEFAULT_PUBLIC_SEED_PATH,
    load_seed_data,
    write_public_seed,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "db"


def _apply_sql_file(conn: psycopg.Connection, path: Path) -> None:
    """Execute one checked-in SQL file against the target database."""
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def render_setup(
    *,
    database_url: str | None = None,
    seed_path: Path = DEFAULT_PUBLIC_SEED_PATH,
    seed_limit: int = 50,
    seed_skip: int = 0,
) -> dict[str, int]:
    """Prepare a demo database with schema, seed data, and semantic indexes."""
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    with psycopg.connect(database_url, autocommit=True) as conn:
        _apply_sql_file(conn, DB_DIR / "init" / "001_extensions.sql")
        _apply_sql_file(conn, DB_DIR / "migrations" / "0001_initial_schema.sql")
        _apply_sql_file(conn, DB_DIR / "migrations" / "0002_embedding_dimension_1024.sql")
        _apply_sql_file(conn, DB_DIR / "migrations" / "0004_embedding_dimension_1024_hnsw.sql")

    write_public_seed(seed_path, limit=seed_limit, skip=seed_skip)
    load_seed_data(seed_path=seed_path, database_url=database_url, truncate_first=True)
    build_semantic_indexes(database_url=database_url)
    return semantic_index_status(database_url=database_url)


def render_setup_cli() -> None:
    """CLI wrapper for Render predeploy bootstrap."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Initialize schema, seed data, and semantic indexes for demo deploys")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--seed-path", type=Path, default=DEFAULT_PUBLIC_SEED_PATH)
    parser.add_argument("--seed-limit", type=int, default=50)
    parser.add_argument("--seed-skip", type=int, default=0)
    args = parser.parse_args()

    status = render_setup(
        database_url=args.database_url,
        seed_path=args.seed_path,
        seed_limit=args.seed_limit,
        seed_skip=args.seed_skip,
    )
    print(json.dumps(status, indent=2))
