"""
LUMINA Advisor Control Panel
══════════════════════════════
Advisors approve, reject, or modify decisions.
Every action is logged in the Merkle audit chain.

Before:
  AI decision → executed automatically
  No human in the loop
  No accountability

After:
  AI decision → advisor sees it → approves/rejects/modifies
  Every advisor action: who, what, when, why
  Merkle-hashed — tamper-evident
  Regulatorily defensible

Advisor workflow:
  1. Morning: open panel → see P0 alerts + pending decisions
  2. Review each decision with full reasoning + twin context
  3. Approve / Reject / Modify
  4. Approved decisions go to ActionEngine
  5. Every step logged with advisor_id + timestamp + hash

This is how banks enforce human oversight on AI actions.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.packages.decision_engine.decision_object import (
    DecisionObject, DecisionPriority, DecisionStatus,
    DecisionRegistry,
)
from lumina.observability.logging import get_logger

logger = get_logger("lumina.advisor_panel")


class AdvisorAction(str, Enum):
    APPROVED        = "approved"
    REJECTED        = "rejected"
    MODIFIED        = "modified"        # changed amount or action
    ESCALATED       = "escalated"       # passed to senior advisor
    DEFERRED        = "deferred"        # review later
    NOTE_ADDED      = "note_added"      # comment without decision


class AdvisorTier(str, Enum):
    RELATIONSHIP_MANAGER = "rm"         # front-line advisor
    SENIOR_ADVISOR       = "senior"     # handles escalations
    COMPLIANCE           = "compliance" # final override authority


@dataclass
class AdvisorProfile:
    advisor_id:   str
    name:         str
    tier:         AdvisorTier
    client_ids:   list[str] = field(default_factory=list)
    max_approve_inr: float  = 5_000_000   # RM: ₹50L limit
                                           # Senior: ₹5Cr
                                           # Compliance: unlimited


@dataclass
class AdvisorAuditEntry:
    """
    Single advisor action in the audit trail.
    Written to Merkle ledger — tamper-evident.
    """
    entry_id:       str   = field(
        default_factory=lambda: f"adv_{uuid.uuid4().hex[:10]}"
    )
    advisor_id:     str   = ""
    advisor_name:   str   = ""
    advisor_tier:   str   = ""
    decision_id:    str   = ""
    user_id:        str   = ""
    action:         str   = ""
    original_amount_inr:  Optional[float] = None
    modified_amount_inr:  Optional[float] = None
    reason:         str   = ""
    note:           str   = ""
    timestamp:      float = field(default_factory=time.time)
    merkle_hash:    str   = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id":             self.entry_id,
            "advisor_id":           self.advisor_id,
            "advisor_name":         self.advisor_name,
            "tier":                 self.advisor_tier,
            "decision_id":          self.decision_id,
            "user_id":              self.user_id,
            "action":               self.action,
            "original_amount_inr":  self.original_amount_inr,
            "modified_amount_inr":  self.modified_amount_inr,
            "reason":               self.reason,
            "note":                 self.note,
            "timestamp":            self.timestamp,
            "merkle_hash":          self.merkle_hash,
        }


@dataclass
class PanelSummary:
    advisor_id:       str
    total_pending:    int
    p0_count:         int
    p1_count:         int
    total_amount_inr: float
    clients_affected: list[str]
    oldest_pending_hrs: float
    decisions:        list[dict]

    def render(self) -> str:
        lines = [
            "╔" + "═" * 54 + "╗",
            f"║  LUMINA ADVISOR PANEL — {self.advisor_id:28}║",
            "╠" + "═" * 54 + "╣",
            f"║  Pending decisions : {self.total_pending:<33}║",
            f"║  P0 (act today)    : {self.p0_count:<33}║",
            f"║  P1 (this week)    : {self.p1_count:<33}║",
            f"║  Total at stake    : "
            f"₹{self.total_amount_inr/1e5:.1f}L{'':<28}║",
            f"║  Clients affected  : "
            f"{len(self.clients_affected):<33}║",
            f"║  Oldest pending    : "
            f"{self.oldest_pending_hrs:.1f}h ago{'':<26}║",
            "╠" + "═" * 54 + "╣",
        ]
        for d in self.decisions[:10]:
            pri   = d.get("priority","")[:2]
            uid   = d.get("user_id","")[:14]
            dtype = d.get("type","")[:20]
            amt   = d.get("amount_inr") or 0
            lines.append(
                f"║  [{pri}] {uid:14} {dtype:20} "
                f"₹{amt/1e3:>5.0f}K  ║"
            )
        lines.append("╚" + "═" * 54 + "╝")
        return "\n".join(lines)


class AdvisorPanel:
    """
    Advisor-facing control panel.

    Advisors interact with this to:
      - See all pending decisions for their clients
      - Approve / reject / modify each decision
      - Add notes to client files
      - Escalate to senior advisor

    Every action writes to:
      1. DecisionObject.status
      2. AdvisorAuditEntry (local log)
      3. Merkle AuditLedger (tamper-evident)

    Amount limits enforced by tier:
      RM         → up to ₹50L without escalation
      Senior     → up to ₹5Cr
      Compliance → unlimited
    """

    def __init__(
        self,
        advisor: AdvisorProfile,
        registry: DecisionRegistry,
        audit_ledger,
    ):
        self.advisor       = advisor
        self.registry      = registry
        self.audit_ledger  = audit_ledger
        self._audit_trail: list[AdvisorAuditEntry] = []

    # ── Panel views ───────────────────────────────────────────────

    def get_summary(self) -> PanelSummary:
        """Morning brief — what needs attention today."""
        pending = self._my_pending()
        p0      = [d for d in pending
                   if d.priority == DecisionPriority.P0]
        p1      = [d for d in pending
                   if d.priority == DecisionPriority.P1]

        total_amt = sum(
            d.amount_inr for d in pending
            if d.amount_inr
        )
        clients = list({d.user_id for d in pending})

        now = time.time()
        oldest_hrs = max(
            (now - d.created_at) / 3600
            for d in pending
        ) if pending else 0.0

        return PanelSummary(
            advisor_id        = self.advisor.advisor_id,
            total_pending     = len(pending),
            p0_count          = len(p0),
            p1_count          = len(p1),
            total_amount_inr  = total_amt,
            clients_affected  = clients,
            oldest_pending_hrs= oldest_hrs,
            decisions         = [d.to_api_dict() for d in pending],
        )

    def get_decision(self, decision_id: str) -> Optional[DecisionObject]:
        d = self.registry.get(decision_id)
        if d and d.user_id in self.advisor.client_ids:
            return d
        return None

    def client_decisions(
        self,
        user_id: str,
        status: Optional[DecisionStatus] = None,
    ) -> list[DecisionObject]:
        if user_id not in self.advisor.client_ids:
            return []
        return self.registry.for_user(user_id, status=status)

    # ── Advisor actions ───────────────────────────────────────────

    def approve(
        self,
        decision_id: str,
        reason: str = "",
        note:   str = "",
    ) -> AdvisorAuditEntry:
        """
        Approve a decision.
        Checks amount limit for advisor tier.
        Writes to Merkle audit ledger.
        """
        decision = self._get_and_validate(decision_id)

        # Amount limit check
        if (
            decision.amount_inr
            and decision.amount_inr > self.advisor.max_approve_inr
        ):
            return self._record(
                decision,
                AdvisorAction.ESCALATED,
                reason = (
                    f"Amount ₹{decision.amount_inr:,.0f} exceeds "
                    f"{self.advisor.tier.value} limit "
                    f"₹{self.advisor.max_approve_inr:,.0f}"
                ),
                note = note,
            )

        decision.approve()

        entry = self._record(
            decision,
            AdvisorAction.APPROVED,
            reason = reason or "Advisor approved",
            note   = note,
        )

        logger.info(
            "advisor.approved",
            advisor_id  = self.advisor.advisor_id,
            decision_id = decision_id,
            user_id     = decision.user_id,
            amount_inr  = decision.amount_inr,
        )
        return entry

    def reject(
        self,
        decision_id: str,
        reason: str,
        note:   str = "",
    ) -> AdvisorAuditEntry:
        """
        Reject a decision. Reason is mandatory.
        """
        if not reason:
            raise ValueError("Rejection reason is mandatory")

        decision = self._get_and_validate(decision_id)
        decision.reject(reason)

        entry = self._record(
            decision,
            AdvisorAction.REJECTED,
            reason = reason,
            note   = note,
        )

        logger.info(
            "advisor.rejected",
            advisor_id  = self.advisor.advisor_id,
            decision_id = decision_id,
            reason      = reason,
        )
        return entry

    def modify_and_approve(
        self,
        decision_id:    str,
        new_amount_inr: float,
        reason:         str,
        note:           str = "",
    ) -> AdvisorAuditEntry:
        """
        Change the amount and approve.
        Both original and modified amounts logged.
        """
        decision = self._get_and_validate(decision_id)
        original = decision.amount_inr

        # Check new amount within tier limit
        if new_amount_inr > self.advisor.max_approve_inr:
            raise ValueError(
                f"Modified amount ₹{new_amount_inr:,.0f} exceeds "
                f"tier limit ₹{self.advisor.max_approve_inr:,.0f}"
            )

        decision.amount_inr = new_amount_inr
        decision.approve()

        entry = self._record(
            decision,
            AdvisorAction.MODIFIED,
            reason               = reason,
            note                 = note,
            original_amount_inr  = original,
            modified_amount_inr  = new_amount_inr,
        )

        logger.info(
            "advisor.modified",
            advisor_id       = self.advisor.advisor_id,
            decision_id      = decision_id,
            original_amount  = original,
            new_amount       = new_amount_inr,
        )
        return entry

    def escalate(
        self,
        decision_id: str,
        reason:      str,
        note:        str = "",
    ) -> AdvisorAuditEntry:
        """
        Pass to senior advisor.
        Decision stays PENDING — not approved yet.
        """
        decision = self._get_and_validate(decision_id)

        entry = self._record(
            decision,
            AdvisorAction.ESCALATED,
            reason = reason,
            note   = note,
        )

        logger.info(
            "advisor.escalated",
            advisor_id  = self.advisor.advisor_id,
            decision_id = decision_id,
            reason      = reason,
        )
        return entry

    def defer(
        self,
        decision_id:      str,
        defer_hours:      float = 24,
        note:             str   = "",
    ) -> AdvisorAuditEntry:
        """
        Defer review. Extends expiry by N hours.
        """
        decision = self._get_and_validate(decision_id)
        new_expiry = time.time() + defer_hours * 3600
        decision.expires_at = new_expiry

        entry = self._record(
            decision,
            AdvisorAction.DEFERRED,
            reason = f"Deferred {defer_hours}h",
            note   = note,
        )

        logger.info(
            "advisor.deferred",
            advisor_id   = self.advisor.advisor_id,
            decision_id  = decision_id,
            defer_hours  = defer_hours,
        )
        return entry

    def add_note(
        self,
        decision_id: str,
        note:        str,
    ) -> AdvisorAuditEntry:
        """Add a note without changing decision status."""
        decision = self.registry.get(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        entry = self._record(
            decision,
            AdvisorAction.NOTE_ADDED,
            reason = "",
            note   = note,
        )
        return entry

    def bulk_approve_p3(self, reason: str = "Bulk approve informational") -> int:
        """
        Approve all P3 (informational) decisions in one action.
        Safe — P3 decisions are low-stakes.
        Returns count approved.
        """
        pending = self._my_pending()
        p3      = [
            d for d in pending
            if d.priority == DecisionPriority.P3
        ]
        for d in p3:
            d.approve()
            self._record(d, AdvisorAction.APPROVED, reason=reason)

        logger.info(
            "advisor.bulk_approved",
            advisor_id = self.advisor.advisor_id,
            count      = len(p3),
        )
        return len(p3)

    # ── Audit trail ───────────────────────────────────────────────

    def audit_trail(
        self,
        user_id:   Optional[str]   = None,
        action:    Optional[str]   = None,
        since_hrs: Optional[float] = None,
    ) -> list[AdvisorAuditEntry]:
        entries = self._audit_trail
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if action:
            entries = [e for e in entries if e.action == action]
        if since_hrs:
            cutoff  = time.time() - since_hrs * 3600
            entries = [e for e in entries if e.timestamp >= cutoff]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def audit_summary(self) -> dict[str, Any]:
        trail   = self._audit_trail
        actions = {}
        for e in trail:
            actions[e.action] = actions.get(e.action, 0) + 1
        return {
            "advisor_id":    self.advisor.advisor_id,
            "total_actions": len(trail),
            "by_action":     actions,
            "clients_served": len({e.user_id for e in trail}),
        }

    # ── Private helpers ───────────────────────────────────────────

    def _my_pending(self) -> list[DecisionObject]:
        return [
            d for d in self.registry.pending()
            if d.user_id in self.advisor.client_ids
        ]

    def _get_and_validate(self, decision_id: str) -> DecisionObject:
        decision = self.registry.get(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.user_id not in self.advisor.client_ids:
            raise PermissionError(
                f"Decision {decision_id} belongs to "
                f"{decision.user_id} — not your client"
            )
        if decision.status not in (
            DecisionStatus.PENDING_ADVISOR,
        ):
            raise ValueError(
                f"Decision already {decision.status.value}"
            )
        return decision

    def _record(
        self,
        decision:            DecisionObject,
        action:              AdvisorAction,
        reason:              str = "",
        note:                str = "",
        original_amount_inr: Optional[float] = None,
        modified_amount_inr: Optional[float] = None,
    ) -> AdvisorAuditEntry:
        """
        Write advisor action to local trail + Merkle ledger.
        """
        entry = AdvisorAuditEntry(
            advisor_id          = self.advisor.advisor_id,
            advisor_name        = self.advisor.name,
            advisor_tier        = self.advisor.tier.value,
            decision_id         = decision.decision_id,
            user_id             = decision.user_id,
            action              = action.value,
            original_amount_inr = original_amount_inr,
            modified_amount_inr = modified_amount_inr,
            reason              = reason,
            note                = note,
        )

        # Write to Merkle ledger
        try:
            from lumina.packages.governance.policy_engine import (
                PolicyDecision, PolicyResult,
            )
            pd = PolicyDecision(
                request_id   = entry.entry_id,
                result       = PolicyResult.ALLOWED,
                receipt_hash = entry.entry_id,
                notes        = f"advisor={self.advisor.advisor_id} "
                               f"action={action.value} "
                               f"reason={reason[:40]}",
            )
            ledger_entry = self.audit_ledger.record(
                pd,
                decision.user_id,
                f"advisor_{action.value}",
            )
            entry.merkle_hash = ledger_entry.entry_hash
        except Exception as e:
            logger.error("panel.audit_write_failed", error=str(e))

        self._audit_trail.append(entry)
        return entry
