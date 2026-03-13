"""
LUMINA Audit Repository
Persists AuditLedger entries to DB.
Merkle chain survives restarts.
In production: 7-year retention per SEBI requirement.
"""
from __future__ import annotations

import time
from typing import Optional

from lumina.observability.logging import get_logger
from lumina.persistence.database import get_connection

logger = get_logger("lumina.persistence.audit")


class AuditRepository:

    def save_entry(self, entry) -> None:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO audit_entries
                (entry_id, user_id, action_type, policy_result,
                 receipt_hash, merkle_position, prev_hash,
                 entry_hash, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.user_id,
                entry.action_type,
                entry.policy_result,
                entry.receipt_hash,
                entry.merkle_position,
                entry.prev_entry_hash,
                entry.entry_hash,
                entry.timestamp,
            ))
        logger.info(
            "audit.saved",
            entry_id = entry.entry_id[:8],
            result   = entry.policy_result,
            hash     = entry.entry_hash[:12],
        )

    def save_event(self, event) -> None:
        import json
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO financial_events
                (event_id, user_id, event_type, severity,
                 source, payload, processed, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.user_id,
                event.event_type.value,
                event.severity.value,
                event.source,
                json.dumps(event.payload),
                int(event.processed),
                event.timestamp,
            ))

    def load_entries_for_user(self, user_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_entries
                WHERE user_id = ?
                ORDER BY merkle_position ASC
            """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def entry_count(self) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM audit_entries"
            ).fetchone()
        return row["cnt"]

    def breakdown(self) -> dict:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT policy_result, COUNT(*) as cnt
                FROM audit_entries
                GROUP BY policy_result
            """).fetchall()
        return {r["policy_result"]: r["cnt"] for r in rows}
