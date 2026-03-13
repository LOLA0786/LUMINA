"""
LUMINA Policy Engine — PrivateVault Integration
Every AI action goes through this. No exceptions.

6 policies checked on every ExecutionRequest:
  1. CONSENT      — does user consent cover this action?
  2. SUITABILITY  — right action for this risk profile?
  3. LIQUIDITY    — will this leave user cash-starved?
  4. CONCENTRATION— would this create dangerous concentration?
  5. AMOUNT_LIMIT — does amount need enhanced review?
  6. FIDUCIARY    — is this genuinely in user's interest?

Receipt hash generated per PrivateVault format —
compatible with pv_merkle_log.py for cross-system audit.
"""
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina.packages.execution_layer.execution_request import ExecutionRequest


class PolicyResult(str, Enum):
    ALLOWED  = "allowed"
    BLOCKED  = "blocked"
    FLAGGED  = "flagged"    # allowed but needs advisor review


class PolicyViolation(str, Enum):
    CONSENT_INSUFFICIENT  = "consent_insufficient"
    SUITABILITY_MISMATCH  = "suitability_mismatch"
    LIQUIDITY_BREACH      = "liquidity_breach"
    CONCENTRATION_RISK    = "concentration_risk"
    AMOUNT_EXCEEDS_LIMIT  = "amount_exceeds_limit"
    FIDUCIARY_BREACH      = "fiduciary_breach"
    REGULATORY_VIOLATION  = "regulatory_violation"


@dataclass
class PolicyDecision:
    decision_id: str                  = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str                   = ""
    result: PolicyResult              = PolicyResult.BLOCKED
    policies_checked: list            = field(default_factory=list)
    violations: list[PolicyViolation] = field(default_factory=list)
    flags: list[str]                  = field(default_factory=list)
    reasoning: str                    = ""
    timestamp: float                  = field(default_factory=time.time)
    receipt_hash: str                 = ""


class PolicyEngine:
    """
    LUMINA's governance gate.

    Wraps PrivateVault's ToolGuard concept with
    financial domain-specific policies.

    In production: receipt_hash feeds into
    PrivateVault's pv_merkle_log.py for
    tamper-evident cross-system audit trail.
    """

    SINGLE_ACTION_LIMIT_INR = 500_000   # ₹5L — enhanced review above this
    MIN_CONFIDENCE_THRESHOLD = 0.60     # below this → advisory only

    def evaluate(
        self,
        request: ExecutionRequest,
        user_profile: dict[str, Any],
    ) -> PolicyDecision:

        decision = PolicyDecision(request_id=request.request_id)
        violations: list[PolicyViolation] = []
        flags: list[str] = []

        # ── Policy 1: Consent ────────────────────────────────────
        decision.policies_checked.append("CONSENT_POLICY")
        consent = user_profile.get("consent_level", "none")
        if consent == "none":
            violations.append(PolicyViolation.CONSENT_INSUFFICIENT)
            decision.reasoning += "No consent granted. "

        # ── Policy 2: Suitability ────────────────────────────────
        decision.policies_checked.append("SUITABILITY_POLICY")
        risk_score = user_profile.get("risk_score", 0.5)
        action = request.action_type.value
        if "rebalance" in action and risk_score < 0.20:
            flags.append(
                f"Conservative user (risk={risk_score:.1f}) — "
                "rebalance requires advisor confirmation."
            )
        if "strong" in action and risk_score < 0.30:
            violations.append(PolicyViolation.SUITABILITY_MISMATCH)
            decision.reasoning += "Action too aggressive for risk profile. "

        # ── Policy 3: Liquidity ──────────────────────────────────
        decision.policies_checked.append("LIQUIDITY_POLICY")
        if request.amount_inr:
            liquid          = user_profile.get("liquid_assets_inr", 0)
            monthly_exp     = user_profile.get("monthly_expenses_inr", 50000)
            emergency_fund  = monthly_exp * 6
            post_liquid     = liquid - request.amount_inr
            if post_liquid < emergency_fund:
                violations.append(PolicyViolation.LIQUIDITY_BREACH)
                decision.reasoning += (
                    f"Post-action liquid ₹{post_liquid:,.0f} < "
                    f"emergency fund ₹{emergency_fund:,.0f}. "
                )

        # ── Policy 4: Concentration ──────────────────────────────
        decision.policies_checked.append("CONCENTRATION_POLICY")
        if request.amount_inr and request.asset_id:
            total = user_profile.get("total_assets_inr", 1)
            conc  = request.amount_inr / total
            if conc > 0.35:
                violations.append(PolicyViolation.CONCENTRATION_RISK)
                decision.reasoning += (
                    f"Single asset would reach {conc:.0%} of portfolio (>35%). "
                )

        # ── Policy 5: Amount limit ───────────────────────────────
        decision.policies_checked.append("AMOUNT_LIMIT_POLICY")
        if request.amount_inr and request.amount_inr > self.SINGLE_ACTION_LIMIT_INR:
            flags.append(
                f"Amount ₹{request.amount_inr:,.0f} exceeds ₹5L — "
                "enhanced review triggered."
            )

        # ── Policy 6: Fiduciary ──────────────────────────────────
        decision.policies_checked.append("FIDUCIARY_POLICY")
        if request.confidence < self.MIN_CONFIDENCE_THRESHOLD:
            flags.append(
                f"Agent confidence {request.confidence:.0%} below "
                f"{self.MIN_CONFIDENCE_THRESHOLD:.0%} — advisory only."
            )

        # ── Final verdict ────────────────────────────────────────
        if violations:
            decision.result     = PolicyResult.BLOCKED
            decision.violations = violations
        elif flags:
            decision.result = PolicyResult.FLAGGED
            decision.flags  = flags
        else:
            decision.result = PolicyResult.ALLOWED

        # ── Receipt hash (PrivateVault-compatible) ───────────────
        receipt_data = {
            "request_id":  request.request_id,
            "user_id":     request.user_id,
            "action":      request.action_type.value,
            "result":      decision.result.value,
            "timestamp":   decision.timestamp,
            "policies":    decision.policies_checked,
            "violations":  [v.value for v in violations],
        }
        decision.receipt_hash = hashlib.sha256(
            json.dumps(receipt_data, sort_keys=True).encode()
        ).hexdigest()

        return decision
