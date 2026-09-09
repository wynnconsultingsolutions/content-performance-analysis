"""
run_sql.py — Execute sql/content_kpis.sql without the sqlite3 CLI.

Run:  python src/run_sql.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "content.db"
SQL = ROOT / "sql" / "content_kpis.sql"


def statements(text: str):
    """Split on semicolons, dropping CLI dot-commands and comment-only blocks."""
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("."))
    for raw in body.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        code = [l for l in stmt.splitlines()
                if l.strip() and not l.strip().startswith("--")]
        if code:
            yield stmt


def main() -> None:
    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", 30)
    text = SQL.read_text()
    with sqlite3.connect(DB) as conn:
        for i, stmt in enumerate(statements(text), 1):
            print("\n" + "=" * 70)
            print(f"QUERY {i}")
            print("=" * 70)
            print(pd.read_sql_query(stmt, conn).to_string(index=False))


if __name__ == "__main__":
    main()
