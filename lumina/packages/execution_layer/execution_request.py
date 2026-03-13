"""
LUMINA Execution Layer
Converts debate outcomes into governed, auditable actions.

Flow:
  DebateOutcome
    → ExecutionRequest  (what, how much, why, confidence)
    → PolicyEngine      (PrivateVault governance gate)
    → User Approval     (if required)
    → ExecutionReceipt  (cryptographic proof, Merkle-logged)

Action types:
  SIP_ADJUST     — increase/decrease monthly SIP
  REBALANCE      — sell X of asset Y, buy Z
  TAX_INVEST     — invest in 80C/NPS before deadline
  ALERT_ADVISOR  — flag for human RM review
  LOAN_REFINANCE — suggest moving loan to lower rate
  INSURANCE_BUY  — suggest new or top-up cover
  GOAL_UPDATE    — revise goal amount or timeline
  EMERGENCY_ALERT— immediate user notification
"""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    SIP_ADJUST       = "sip_adjust"
    REBALANCE        = "rebalance"
    TAX_INVEST       = "tax_invest"
    ALERT_ADVISOR    = "alert_advisor"
    LOAN_REFINANCE   = "loan_refinance"
    INSURANCE_BUY    = "insurance_buy"
    GOAL_UPDATE      = "goal_update"
    EMERGENCY_ALERT  = "emergency_alert"


class ExecutionStatus(str, Enum):
    PENDING_GOVERNANCE = "pending_governance"
    PENDING_APPROVAL   = "pending_approval"
    APPROVED           = "approved"
    EXECUTED           = "executed"
    REJECTED           = "rejected"
    BLOCKED            = "blocked"


@dataclass
class ExecutionRequest:
    request_id: str              = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str                 = ""
    action_type: ActionType      = ActionType.ALERT_ADVISOR
    description: str             = ""
    amount_inr: Optional[float]  = None
    asset_id: Optional[str]      = None
    metadata: dict[str, Any]     = field(default_factory=dict)
    triggered_by_event: Optional[str] = None
    agent_recommendation: str    = ""
    confidence: float            = 0.0
    status: ExecutionStatus      = ExecutionStatus.PENDING_GOVERNANCE
    created_at: float            = field(default_factory=time.time)


@dataclass
class ExecutionReceipt:
    """
    Cryptographic proof that an action was decided upon.
    Feeds directly into PrivateVault Merkle transparency log.
    Every receipt is tamper-evident and independently verifiable.
    """
    receipt_id: str           = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str           = ""
    user_id: str              = ""
    action_type: str          = ""
    status: ExecutionStatus   = ExecutionStatus.EXECUTED
    governance_result: str    = ""
    policy_checked: list      = field(default_factory=list)
    executed_at: float        = field(default_factory=time.time)
    merkle_hash: Optional[str]= None
    advisor_notified: bool    = False

    def summary(self) -> str:
        return (
            f"Receipt {self.receipt_id[:8]} | "
            f"action={self.action_type} | "
            f"status={self.status.value} | "
            f"governance={self.governance_result} | "
            f"hash={self.merkle_hash[:12] if self.merkle_hash else 'pending'}..."
        )
