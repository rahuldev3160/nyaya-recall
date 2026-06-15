"""Shared DB connection helper — enables WAL mode and busy timeout on every connection."""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA foreign_keys=ON")
    con.row_factory = sqlite3.Row
    return con


def enable_wal(db_path: str | None = None) -> None:
    """One-time call at startup to make WAL mode durable for the DB file."""
    con = get_conn(db_path)
    con.close()
