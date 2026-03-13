"""
LUMINA Decision Objects
════════════════════════
The most important missing layer.

Right now agents output logs and summaries.
This makes them machine-readable decisions.

Before:
  agent → "Liquidity is low, consider building emergency fund"

After:
  agent → DecisionObject {
    decision_id:    "dec_8821"
    user_id:        "vikram_nair"
    type:           LIQUIDITY_ADJUSTMENT
    priority:       P0
    action:         INCREASE_EMERGENCY_FUND
    amount_inr:     150000
    confidence:     0.92
    trigger_event:  "goal_at_risk"
    reasoning:      "Liquid ₹45K below 6-month fund ₹3.3L"
    assumptions:    ["monthly_expenses=₹55K", "6mo buffer"]
    policy_result:  ALLOWED
    audit_hash:     "a487e29e..."
  }

This allows banks, advisors, fintech apps
to consume decisions via API — not just read summaries.

Without this: analysis system.
With this:    automation infrastructure.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DecisionType(str, Enum):
    # Liquidity
    LIQUIDITY_ADJUSTMENT     = "liquidity_adjustment"
    EMERGENCY_FUND_BUILD     = "emergency_fund_build"

    # Investment
    SIP_INCREASE             = "sip_increase"
    SIP_DECREASE             = "sip_decrease"
    PORTFOLIO_REBALANCE      = "portfolio_rebalance"
    LUMPSUM_INVEST           = "lumpsum_invest"

    # Tax
    TAX_REGIME_SWITCH        = "tax_regime_switch"
    TAX_SAVING_INVEST        = "tax_saving_invest"
    ADVANCE_TAX_ALERT        = "advance_tax_alert"

    # Debt
    LOAN_PREPAYMENT          = "loan_prepayment"
    LOAN_REFINANCE           = "loan_refinance"
    CLOSE_HIGH_INTEREST_LOAN = "close_high_interest_loan"

    # Protection
    INSURANCE_GAP_ALERT      = "insurance_gap_alert"
    INSURANCE_BUY            = "insurance_buy"

    # Retirement
    RETIREMENT_SIP_BOOST     = "retirement_sip_boost"
    RETIREMENT_GOAL_REVISION = "retirement_goal_revision"

    # Risk
    CONCENTRATION_ALERT      = "concentration_alert"
    DRAWDOWN_ALERT           = "drawdown_alert"

    # Advisory
    ADVISOR_REVIEW_NEEDED    = "advisor_review_needed"
    NO_ACTION_NEEDED         = "no_action_needed"


class DecisionPriority(str, Enum):
    P0 = "P0_IMMEDIATE"      # act today
    P1 = "P1_THIS_WEEK"
    P2 = "P2_THIS_MONTH"
    P3 = "P3_INFORMATIONAL"


class DecisionStatus(str, Enum):
    PENDING_ADVISOR   = "pending_advisor"
    APPROVED          = "approved"
    REJECTED          = "rejected"
    EXECUTED          = "executed"
    EXPIRED           = "expired"
    AUTO_APPROVED     = "auto_approved"


class ActionVerb(str, Enum):
    INCREASE_SIP          = "increase_sip"
    DECREASE_SIP          = "decrease_sip"
    REBALANCE_PORTFOLIO   = "rebalance_portfolio"
    REDIRECT_BONUS        = "redirect_bonus"
    PREPAY_LOAN           = "prepay_loan"
    REFINANCE_LOAN        = "refinance_loan"
    SWITCH_TAX_REGIME     = "switch_tax_regime"
    INVEST_80C            = "invest_80c"
    BUY_INSURANCE         = "buy_insurance"
    ALERT_ADVISOR         = "alert_advisor"
    NO_ACTION             = "no_action"


@dataclass
class DecisionObject:
    """
    A single machine-readable financial decision.

    This is the atomic unit of LUMINA's output.
    Everything downstream — action engine, advisor panel,
    API, audit log — consumes DecisionObjects.

    Banks and fintech apps call GET /decisions
    and get a list of these. They don't need to
    understand LUMINA's internals. Just the decision.
    """
    decision_id:      str               = field(
        default_factory=lambda: f"dec_{uuid.uuid4().hex[:8]}"
    )
    user_id:          str               = ""
    decision_type:    DecisionType      = DecisionType.NO_ACTION_NEEDED
    priority:         DecisionPriority  = DecisionPriority.P3
    action:           ActionVerb        = ActionVerb.NO_ACTION
    amount_inr:       Optional[float]   = None
    asset_id:         Optional[str]     = None
    confidence:       float             = 0.0
    trigger_event:    Optional[str]     = None
    triggered_by_agent: str            = ""
    reasoning:        str               = ""
    assumptions:      list[str]         = field(default_factory=list)
    policy_result:    str               = "pending"
    audit_hash:       Optional[str]     = None
    status:           DecisionStatus    = DecisionStatus.PENDING_ADVISOR
    created_at:       float             = field(default_factory=time.time)
    expires_at:       Optional[float]   = None
    metadata:         dict[str, Any]    = field(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        """
        Clean dict for API responses.
        This is what banks and advisors consume.
        """
        return {
            "decision_id":        self.decision_id,
            "user_id":            self.user_id,
            "type":               self.decision_type.value,
            "priority":           self.priority.value,
            "action":             self.action.value,
            "amount_inr":         self.amount_inr,
            "confidence":         round(self.confidence, 3),
            "trigger_event":      self.trigger_event,
            "triggered_by_agent": self.triggered_by_agent,
            "reasoning":          self.reasoning,
            "assumptions":        self.assumptions,
            "policy_result":      self.policy_result,
            "audit_hash":         self.audit_hash,
            "status":             self.status.value,
            "created_at":         self.created_at,
            "expires_at":         self.expires_at,
        }

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def approve(self) -> None:
        self.status = DecisionStatus.APPROVED

    def reject(self, reason: str = "") -> None:
        self.status = DecisionStatus.REJECTED
        if reason:
            self.metadata["rejection_reason"] = reason

    def mark_executed(self, audit_hash: str) -> None:
        self.status    = DecisionStatus.EXECUTED
        self.audit_hash = audit_hash


class DecisionBuilder:
    """
    Fluent builder for DecisionObjects.
    Agents use this to produce typed decisions.

    Usage:
        decision = (
            DecisionBuilder("vikram_nair")
            .type(DecisionType.EMERGENCY_FUND_BUILD)
            .priority(DecisionPriority.P0)
            .action(ActionVerb.REDIRECT_BONUS)
            .amount(150000)
            .confidence(0.92)
            .triggered_by("goal_at_risk", "risk_agent")
            .reason("Liquid ₹45K below 6mo fund ₹3.3L")
            .assume("monthly_expenses=₹55K")
            .assume("6 month buffer required")
            .build()
        )
    """

    def __init__(self, user_id: str):
        self._d = DecisionObject(user_id=user_id)

    def type(self, t: DecisionType) -> DecisionBuilder:
        self._d.decision_type = t
        return self

    def priority(self, p: DecisionPriority) -> DecisionBuilder:
        self._d.priority = p
        return self

    def action(self, a: ActionVerb) -> DecisionBuilder:
        self._d.action = a
        return self

    def amount(self, inr: float) -> DecisionBuilder:
        self._d.amount_inr = inr
        return self

    def asset(self, asset_id: str) -> DecisionBuilder:
        self._d.asset_id = asset_id
        return self

    def confidence(self, c: float) -> DecisionBuilder:
        self._d.confidence = max(0.0, min(1.0, c))
        return self

    def triggered_by(
        self, event: str, agent: str
    ) -> DecisionBuilder:
        self._d.trigger_event      = event
        self._d.triggered_by_agent = agent
        return self

    def reason(self, text: str) -> DecisionBuilder:
        self._d.reasoning = text
        return self

    def assume(self, assumption: str) -> DecisionBuilder:
        self._d.assumptions.append(assumption)
        return self

    def expires_in(self, seconds: float) -> DecisionBuilder:
        self._d.expires_at = time.time() + seconds
        return self

    def meta(self, key: str, value: Any) -> DecisionBuilder:
        self._d.metadata[key] = value
        return self

    def build(self) -> DecisionObject:
        return self._d


class DecisionRegistry:
    """
    In-memory store of all decisions.
    In production: backed by DB table.

    Consumers (banks, advisors, apps) query this.
    """

    def __init__(self):
        self._decisions: dict[str, DecisionObject] = {}

    def register(self, decision: DecisionObject) -> DecisionObject:
        self._decisions[decision.decision_id] = decision
        return decision

    def get(self, decision_id: str) -> Optional[DecisionObject]:
        return self._decisions.get(decision_id)

    def for_user(
        self,
        user_id: str,
        status: Optional[DecisionStatus] = None,
        priority: Optional[DecisionPriority] = None,
    ) -> list[DecisionObject]:
        results = [
            d for d in self._decisions.values()
            if d.user_id == user_id and not d.is_expired()
        ]
        if status:
            results = [d for d in results if d.status == status]
        if priority:
            results = [d for d in results if d.priority == priority]
        return sorted(results, key=lambda d: d.created_at, reverse=True)

    def pending(self) -> list[DecisionObject]:
        return [
            d for d in self._decisions.values()
            if d.status == DecisionStatus.PENDING_ADVISOR
            and not d.is_expired()
        ]

    def p0_decisions(self) -> list[DecisionObject]:
        return [
            d for d in self._decisions.values()
            if d.priority == DecisionPriority.P0
            and d.status == DecisionStatus.PENDING_ADVISOR
            and not d.is_expired()
        ]

    def summary(self) -> dict[str, Any]:
        all_d = list(self._decisions.values())
        return {
            "total":    len(all_d),
            "pending":  sum(
                1 for d in all_d
                if d.status == DecisionStatus.PENDING_ADVISOR
            ),
            "approved": sum(
                1 for d in all_d
                if d.status == DecisionStatus.APPROVED
            ),
            "executed": sum(
                1 for d in all_d
                if d.status == DecisionStatus.EXECUTED
            ),
            "rejected": sum(
                1 for d in all_d
                if d.status == DecisionStatus.REJECTED
            ),
            "p0_count": len(self.p0_decisions()),
        }
