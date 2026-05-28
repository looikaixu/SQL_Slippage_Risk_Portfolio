from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "slippage_risk.db"
SQL_FILES = [
    PROJECT_DIR / "sql" / "01_schema.sql",
    PROJECT_DIR / "sql" / "02_seed_data.sql",
    PROJECT_DIR / "sql" / "03_risk_views.sql",
]


def build_database(db_path: Path = DB_PATH) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        for sql_file in SQL_FILES:
            conn.executescript(sql_file.read_text(encoding="utf-8"))

    return db_path


if __name__ == "__main__":
    path = build_database()
    print(f"Created SQLite database: {path}")
