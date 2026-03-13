"""
LUMINA Database Layer
SQLite in dev. Postgres in prod. Same interface, swap the URL.

Tables:
  users            — user registry
  twin_snapshots   — every financial state snapshot (append-only)
  audit_entries    — every governance decision (append-only)
  financial_events — every event fired (append-only)

All tables are append-only by design.
Nothing is ever deleted. Nothing is ever updated in place.
This matches the immutable architecture of the Digital Twin
and the Merkle audit ledger.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from lumina.config.settings import settings
from lumina.observability.logging import get_logger

logger = get_logger("lumina.persistence")


def _db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return "lumina.db"


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    path = _db_path()
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      TEXT PRIMARY KEY,
                age          INTEGER NOT NULL,
                risk_score   REAL    NOT NULL,
                created_at   REAL    NOT NULL,
                updated_at   REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS twin_snapshots (
                snapshot_id   TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                timestamp     REAL NOT NULL,
                state_hash    TEXT NOT NULL,
                net_worth_inr REAL NOT NULL,
                total_assets  REAL NOT NULL,
                total_liabs   REAL NOT NULL,
                payload       TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS audit_entries (
                entry_id        TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                action_type     TEXT NOT NULL,
                policy_result   TEXT NOT NULL,
                receipt_hash    TEXT NOT NULL,
                merkle_position INTEGER NOT NULL,
                prev_hash       TEXT NOT NULL,
                entry_hash      TEXT NOT NULL,
                timestamp       REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS financial_events (
                event_id    TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                severity    TEXT NOT NULL,
                source      TEXT NOT NULL,
                payload     TEXT NOT NULL,
                processed   INTEGER NOT NULL DEFAULT 0,
                timestamp   REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_user
                ON twin_snapshots(user_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_user
                ON audit_entries(user_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_user
                ON financial_events(user_id, timestamp);
        """)
    logger.info("db.initialized", path=_db_path())
