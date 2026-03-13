"""
LUMINA Audit Ledger — Merkle Transparency Log
Append-only. Hash-linked. Tamper-evident.

Every governance decision is recorded here.
If any entry is modified, the Merkle root changes.
Auditors can verify LUMINA's entire decision history.

In production: feeds into PrivateVault's pv_merkle_log.py
for cross-system tamper-evident audit trails.

Compatible receipt format with PrivateVault's pv_receipt.py.
"""
from __future__ import annotations
import hashlib, json, time
from dataclasses import dataclass, field
from typing import Optional

from lumina.packages.governance.policy_engine import PolicyDecision


@dataclass
class LedgerEntry:
    entry_id: str
    user_id: str
    action_type: str
    policy_result: str
    receipt_hash: str
    timestamp: float
    merkle_position: int
    prev_entry_hash: str = "genesis"
    entry_hash: str      = ""

    def compute_hash(self) -> str:
        data = {
            "entry_id":       self.entry_id,
            "user_id":        self.user_id,
            "action_type":    self.action_type,
            "policy_result":  self.policy_result,
            "receipt_hash":   self.receipt_hash,
            "timestamp":      self.timestamp,
            "prev":           self.prev_entry_hash,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


class AuditLedger:
    """
    Append-only audit ledger with Merkle verification.

    Structure mirrors PrivateVault's Merkle log:
      Entry hashes → Merkle tree → Merkle root

    The root is a cryptographic fingerprint of all decisions.
    One tampered entry → root mismatch → detected instantly.
    """

    def __init__(self):
        self._entries: list[LedgerEntry] = []
        self._merkle_root: Optional[str] = None

    def record(
        self,
        decision: PolicyDecision,
        user_id: str,
        action_type: str,
    ) -> LedgerEntry:
        prev_hash = (
            self._entries[-1].entry_hash
            if self._entries else "genesis"
        )
        entry = LedgerEntry(
            entry_id        = decision.decision_id,
            user_id         = user_id,
            action_type     = action_type,
            policy_result   = decision.result.value,
            receipt_hash    = decision.receipt_hash,
            timestamp       = decision.timestamp,
            merkle_position = len(self._entries),
            prev_entry_hash = prev_hash,
        )
        entry.entry_hash  = entry.compute_hash()
        self._entries.append(entry)
        self._merkle_root = self._build_merkle_root()
        return entry

    def _build_merkle_root(self) -> str:
        if not self._entries:
            return hashlib.sha256(b"empty").hexdigest()
        hashes = [e.entry_hash for e in self._entries]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256(
                    (hashes[i] + hashes[i + 1]).encode()
                ).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]

    def verify_integrity(self) -> bool:
        """Full chain verification — O(n)."""
        for i, entry in enumerate(self._entries):
            expected_prev = (
                self._entries[i - 1].entry_hash if i > 0 else "genesis"
            )
            if entry.prev_entry_hash != expected_prev:
                return False
            if entry.entry_hash != entry.compute_hash():
                return False
        return True

    @property
    def merkle_root(self) -> Optional[str]:
        return self._merkle_root

    def entries_for_user(self, user_id: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.user_id == user_id]

    def summary(self) -> dict:
        return {
            "total_entries": len(self._entries),
            "merkle_root":   self._merkle_root,
            "chain_valid":   self.verify_integrity(),
            "breakdown": {
                "allowed": sum(
                    1 for e in self._entries if e.policy_result == "allowed"
                ),
                "blocked": sum(
                    1 for e in self._entries if e.policy_result == "blocked"
                ),
                "flagged": sum(
                    1 for e in self._entries if e.policy_result == "flagged"
                ),
            },
        }
