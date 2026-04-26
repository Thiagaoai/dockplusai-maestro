"""Apply MAESTRO Supabase schema.

Usage:
    SUPABASE_DB_URL='postgresql://...' python scripts/apply_supabase_schema.py

This uses the direct Postgres connection string from Supabase:
Project Settings -> Database -> Connection string -> URI.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg


def main() -> None:
    database_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("Missing SUPABASE_DB_URL or DATABASE_URL")

    sql_path = Path(__file__).with_name("seed_supabase.sql")
    sql = sql_path.read_text(encoding="utf-8")

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

    print(f"Applied schema from {sql_path}")


if __name__ == "__main__":
    main()
