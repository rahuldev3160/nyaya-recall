"""Shared DB connection helper for scripts — mirrors backend/db.py."""
from __future__ import annotations
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.row_factory = sqlite3.Row
    return con
