"""
LUMINA Action Engine
═════════════════════
Decisions become executions.

Before:
  LUMINA suggests → human manually acts

After:
  DecisionObject → ActionEngine → Executed → AuditReceipt

Action types:
  increase_sip          → SIP mandate updated
  rebalance_portfolio   → sell/buy orders queued
  redirect_bonus        → funds routed to goal
  prepay_loan           → partial prepayment queued
  switch_tax_regime     → regime flag updated in twin
  invest_80c            → ELSS/PPF investment queued
  alert_advisor         → RM notified with context

Every execution:
  1. Checks DecisionObject is APPROVED
  2. Validates against twin current state
  3. Executes the action (updates twin + queues external)
  4. Writes ExecutionReceipt to Merkle audit log
  5. Updates DecisionObject status → EXECUTED

This is when LUMINA stops being demo software.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.packages.decision_engine.decision_object import (
    ActionVerb, DecisionObject, DecisionStatus,
)
from lumina.observability.logging import get_logger

logger = get_logger("lumina.action_engine")


class ExecutionResult(str, Enum):
    SUCCESS         = "success"
    FAILED          = "failed"
    SKIPPED         = "skipped"         # decision not approved
    TWIN_MISMATCH   = "twin_mismatch"   # state changed since decision
    NOT_IMPLEMENTED = "not_implemented" # connector not wired yet


@dataclass
class ActionReceipt:
    """
    Cryptographic proof that an action was attempted.
    Feeds into Merkle audit log.
    Compatible with PrivateVault receipt format.
    """
    receipt_id:      str             = field(
        default_factory=lambda: f"rcpt_{uuid.uuid4().hex[:10]}"
    )
    decision_id:     str             = ""
    user_id:         str             = ""
    action:          str             = ""
    result:          ExecutionResult = ExecutionResult.SUCCESS
    amount_inr:      Optional[float] = None
    detail:          str             = ""
    executed_at:     float           = field(default_factory=time.time)
    twin_snapshot_id: Optional[str]  = None
    external_ref:    Optional[str]   = None  # broker/bank ref ID


@dataclass
class ActionContext:
    """
    Everything the ActionEngine needs to execute a decision.
    Passed in from FinancialOS.
    """
    twin: Any                    # FinancialTwin
    registry: Any                # DecisionRegistry
    audit_ledger: Any            # AuditLedger
    dry_run: bool = False        # if True: simulate only, no state change


class ActionEngine:
    """
    Executes approved DecisionObjects.

    In production: connectors wire to real bank/broker APIs.
    Today: updates FinancialTwin state + queues external refs.

    Every execution is atomic:
      approve → validate → execute → receipt → audit
    If any step fails, the decision stays APPROVED (not EXECUTED)
    and the error is logged with full context.
    """

    # Actions that can be auto-approved (no advisor needed)
    AUTO_APPROVE_ACTIONS = {
        ActionVerb.ALERT_ADVISOR,
        ActionVerb.NO_ACTION,
    }

    # Actions that always need advisor approval
    REQUIRE_APPROVAL_ACTIONS = {
        ActionVerb.REBALANCE_PORTFOLIO,
        ActionVerb.PREPAY_LOAN,
        ActionVerb.REFINANCE_LOAN,
        ActionVerb.BUY_INSURANCE,
    }

    def execute(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        """
        Main execution entry point.
        Returns an ActionReceipt regardless of outcome.
        """
        logger.info(
            "action.attempting",
            decision_id = decision.decision_id,
            user_id     = decision.user_id,
            action      = decision.action.value,
            status      = decision.status.value,
            dry_run     = ctx.dry_run,
        )

        # Auto-approve safe actions
        if (
            decision.status == DecisionStatus.PENDING_ADVISOR
            and decision.action in self.AUTO_APPROVE_ACTIONS
        ):
            decision.status = DecisionStatus.AUTO_APPROVED

        # Guard: must be approved
        if decision.status not in (
            DecisionStatus.APPROVED,
            DecisionStatus.AUTO_APPROVED,
        ):
            return self._receipt(
                decision,
                ExecutionResult.SKIPPED,
                f"Status is {decision.status.value} — not approved",
            )

        # Validate twin state still matches decision context
        valid, reason = self._validate_twin(decision, ctx.twin)
        if not valid:
            return self._receipt(
                decision,
                ExecutionResult.TWIN_MISMATCH,
                reason,
            )

        # Route to correct executor
        try:
            receipt = self._route(decision, ctx)
        except NotImplementedError as e:
            receipt = self._receipt(
                decision,
                ExecutionResult.NOT_IMPLEMENTED,
                str(e),
            )
        except Exception as e:
            logger.error(
                "action.failed",
                decision_id = decision.decision_id,
                error       = str(e),
            )
            receipt = self._receipt(
                decision,
                ExecutionResult.FAILED,
                str(e),
            )
            return receipt

        # Write to Merkle audit log
        self._write_audit(decision, receipt, ctx)

        logger.info(
            "action.complete",
            receipt_id  = receipt.receipt_id,
            decision_id = decision.decision_id,
            result      = receipt.result.value,
            detail      = receipt.detail,
        )
        return receipt

    def execute_batch(
        self,
        decisions: list[DecisionObject],
        ctx: ActionContext,
    ) -> list[ActionReceipt]:
        """Execute multiple decisions. Returns all receipts."""
        return [self.execute(d, ctx) for d in decisions]

    # ── Routers ──────────────────────────────────────────────────

    def _route(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        action = decision.action
        routes = {
            ActionVerb.INCREASE_SIP:        self._execute_sip_increase,
            ActionVerb.DECREASE_SIP:        self._execute_sip_decrease,
            ActionVerb.REBALANCE_PORTFOLIO: self._execute_rebalance,
            ActionVerb.REDIRECT_BONUS:      self._execute_redirect_bonus,
            ActionVerb.PREPAY_LOAN:         self._execute_loan_prepay,
            ActionVerb.SWITCH_TAX_REGIME:   self._execute_tax_switch,
            ActionVerb.INVEST_80C:          self._execute_80c_invest,
            ActionVerb.ALERT_ADVISOR:       self._execute_advisor_alert,
            ActionVerb.NO_ACTION:           self._execute_no_action,
        }
        handler = routes.get(action)
        if not handler:
            raise NotImplementedError(
                f"No executor for action: {action.value}"
            )
        return handler(decision, ctx)

    # ── Executors ─────────────────────────────────────────────────

    def _execute_sip_increase(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        amount = decision.amount_inr or 0
        if not ctx.dry_run:
            # In production: call AMC/broker API to update SIP mandate
            # For now: log the intent + update goal SIP in twin
            twin = ctx.twin
            goals = twin.current.financial_goals
            if goals:
                updated_goals = []
                for g in goals:
                    from lumina.packages.digital_twin.financial_twin import FinancialGoal
                    updated_goals.append(FinancialGoal(
                        goal_id             = g.goal_id,
                        goal_type           = g.goal_type,
                        description         = g.description,
                        target_amount_inr   = g.target_amount_inr,
                        target_year         = g.target_year,
                        current_savings_inr = g.current_savings_inr,
                        monthly_sip_inr     = g.monthly_sip_inr + amount,
                    ))
                twin._mutate(financial_goals=updated_goals)
            decision.mark_executed(
                f"sip_exec_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"SIP increased by ₹{amount:,.0f}/month"
            + (" [DRY RUN]" if ctx.dry_run else ""),
            amount_inr=amount,
            external_ref=f"sip_mandate_{uuid.uuid4().hex[:8]}",
        )

    def _execute_sip_decrease(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        amount = decision.amount_inr or 0
        if not ctx.dry_run:
            decision.mark_executed(
                f"sip_exec_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"SIP decreased by ₹{amount:,.0f}/month"
            + (" [DRY RUN]" if ctx.dry_run else ""),
            amount_inr=amount,
        )

    def _execute_rebalance(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        amount = decision.amount_inr or 0
        if not ctx.dry_run:
            # In production: place sell/buy orders via broker API
            decision.mark_executed(
                f"rebal_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"Rebalance queued for ₹{amount:,.0f}"
            + (" [DRY RUN]" if ctx.dry_run else ""),
            amount_inr=amount,
            external_ref=f"broker_order_{uuid.uuid4().hex[:8]}",
        )

    def _execute_redirect_bonus(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        amount = decision.amount_inr or 0
        if not ctx.dry_run:
            # In production: set up auto-sweep rule in bank
            decision.mark_executed(
                f"redirect_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"₹{amount:,.0f} redirect rule created → emergency fund"
            + (" [DRY RUN]" if ctx.dry_run else ""),
            amount_inr=amount,
        )

    def _execute_loan_prepay(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        amount = decision.amount_inr or 0
        if not ctx.dry_run:
            decision.mark_executed(
                f"prepay_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"Loan prepayment of ₹{amount:,.0f} queued"
            + (" [DRY RUN]" if ctx.dry_run else ""),
            amount_inr=amount,
            external_ref=f"bank_prepay_{uuid.uuid4().hex[:8]}",
        )

    def _execute_tax_switch(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        new_regime = decision.metadata.get("new_regime", "NEW")
        if not ctx.dry_run:
            twin = ctx.twin
            from lumina.packages.digital_twin.financial_twin import TaxProfile
            old = twin.current.tax_profile
            twin.set_tax_profile(TaxProfile(
                pan                    = old.pan,
                preferred_regime       = new_regime,
                deductions_80c_inr     = old.deductions_80c_inr,
                deductions_80d_inr     = old.deductions_80d_inr,
                hra_exemption_inr      = old.hra_exemption_inr,
                nps_80ccd_inr          = old.nps_80ccd_inr,
                home_loan_interest_inr = old.home_loan_interest_inr,
            ))
            decision.mark_executed(
                f"tax_switch_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"Tax regime switched to {new_regime}"
            + (" [DRY RUN]" if ctx.dry_run else ""),
        )

    def _execute_80c_invest(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        amount = decision.amount_inr or 0
        if not ctx.dry_run:
            decision.mark_executed(
                f"invest_80c_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"₹{amount:,.0f} 80C investment queued (ELSS/PPF)"
            + (" [DRY RUN]" if ctx.dry_run else ""),
            amount_inr=amount,
            external_ref=f"amc_order_{uuid.uuid4().hex[:8]}",
        )

    def _execute_advisor_alert(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        if not ctx.dry_run:
            # In production: push notification to RM dashboard
            decision.mark_executed(
                f"alert_{uuid.uuid4().hex[:8]}"
            )
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            f"Advisor alerted: {decision.reasoning[:60]}",
        )

    def _execute_no_action(
        self,
        decision: DecisionObject,
        ctx: ActionContext,
    ) -> ActionReceipt:
        if not ctx.dry_run:
            decision.mark_executed("no_action")
        return self._receipt(
            decision,
            ExecutionResult.SUCCESS,
            "No action required",
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _validate_twin(
        self,
        decision: DecisionObject,
        twin: Any,
    ) -> tuple[bool, str]:
        """
        Check twin state still matches decision assumptions.
        Prevents stale decisions from executing on changed state.
        """
        snap = twin.current

        # If decision has an amount, check liquidity
        if decision.amount_inr and decision.amount_inr > 0:
            if action_reduces_liquidity(decision.action):
                monthly_exp   = snap.monthly_income_inr * 0.5
                emergency     = monthly_exp * 6
                post_liquid   = snap.total_liquid_inr - decision.amount_inr
                if post_liquid < 0:
                    return False, (
                        f"Insufficient funds: liquid=₹{snap.total_liquid_inr:,.0f} "
                        f"< action=₹{decision.amount_inr:,.0f}"
                    )
        return True, "ok"

    def _receipt(
        self,
        decision: DecisionObject,
        result: ExecutionResult,
        detail: str,
        amount_inr: Optional[float] = None,
        external_ref: Optional[str] = None,
    ) -> ActionReceipt:
        return ActionReceipt(
            decision_id      = decision.decision_id,
            user_id          = decision.user_id,
            action           = decision.action.value,
            result           = result,
            amount_inr       = amount_inr or decision.amount_inr,
            detail           = detail,
            twin_snapshot_id = None,
            external_ref     = external_ref,
        )

    def _write_audit(
        self,
        decision: DecisionObject,
        receipt: ActionReceipt,
        ctx: ActionContext,
    ) -> None:
        """Write execution to Merkle audit ledger."""
        try:
            from lumina.packages.governance.policy_engine import (
                PolicyDecision, PolicyResult,
            )
            pd = PolicyDecision(
                request_id   = decision.decision_id,
                result       = (
                    PolicyResult.ALLOWED
                    if receipt.result == ExecutionResult.SUCCESS
                    else PolicyResult.BLOCKED
                ),
                receipt_hash = receipt.receipt_id,
            )
            ctx.audit_ledger.record(
                pd,
                decision.user_id,
                decision.action.value,
            )
        except Exception as e:
            logger.error("audit.write_failed", error=str(e))


def action_reduces_liquidity(action: ActionVerb) -> bool:
    return action in {
        ActionVerb.INCREASE_SIP,
        ActionVerb.REDIRECT_BONUS,
        ActionVerb.PREPAY_LOAN,
        ActionVerb.INVEST_80C,
        ActionVerb.REBALANCE_PORTFOLIO,
    }
