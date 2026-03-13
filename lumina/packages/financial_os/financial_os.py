"""
LUMINA Financial Operating System
The control plane of finance.

Wires everything together:
  FinancialTwin  → permanent state machine
  EventBus       → event-driven reactions
  DebateEngine   → multi-agent collaboration
  PolicyEngine   → PrivateVault governance
  AuditLedger    → Merkle-hashed audit trail
  AdvisorBrief   → RM dashboard

Event → Debate → Policy → Ledger → Approval → Receipt
"""
from __future__ import annotations
import logging, time
from dataclasses import dataclass, field
from typing import Any, Optional

from lumina.packages.autonomous_agents.agent_debate import (
    AgentArgument, AgentPosition, DebateEngine, DebateOutcome,
)
from lumina.packages.digital_twin.financial_twin import FinancialTwin, TwinSnapshot
from lumina.packages.event_engine.event_bus import EventBus
from lumina.packages.event_engine.financial_events import FinancialEvent
from lumina.packages.execution_layer.execution_request import (
    ActionType, ExecutionRequest, ExecutionStatus,
)
from lumina.packages.governance.audit_ledger import AuditLedger
from lumina.packages.governance.policy_engine import PolicyEngine, PolicyResult
from lumina.packages.event_engine.event_reactor import EventReactor
from lumina.packages.advisor_layer.advisor_brief import (
    AdvisorBrief, AlertPriority, ClientAlert,
)

logger = logging.getLogger("lumina.os")


@dataclass
class OSSession:
    user_id: str
    twin: FinancialTwin
    events_processed: int = 0
    actions_executed: int = 0
    actions_blocked: int  = 0
    session_start: float  = field(default_factory=time.time)


class FinancialOS:
    """
    The Financial Operating System.
    Single entry point for all LUMINA capabilities.
    """

    def __init__(self):
        self.event_bus     = EventBus()
        self.debate_engine = DebateEngine()
        self.policy_engine = PolicyEngine()
        self.audit_ledger  = AuditLedger()
        self._sessions: dict[str, OSSession] = {}
        self._agents: dict[str, Any] = {}
        self.reactor = EventReactor(self)
        self.reactor.wire()
        logger.info("[FinancialOS] Initialized")

    def register_agent(self, name: str, agent: Any) -> None:
        self._agents[name] = agent

    def onboard_user(self, twin: FinancialTwin) -> OSSession:
        session = OSSession(user_id=twin.user_id, twin=twin)
        self._sessions[twin.user_id] = session
        logger.info(
            "[FinancialOS] Onboarded user=%s nw=₹%.0f",
            twin.user_id, twin.current.net_worth_inr,
        )
        return session

    def process_event(self, event: FinancialEvent) -> dict[str, Any]:
        """
        Main pipeline:
        Event → EventBus → Debate → PolicyEngine → AuditLedger → Result
        """
        session = self._sessions.get(event.user_id)
        if not session:
            return {"status": "error", "reason": "user_not_onboarded"}

        logger.info(
            "[FinancialOS] Event=%s user=%s", event.event_type, event.user_id
        )

        # 1. Route to subscribed handlers
        self.event_bus.publish(event)

        # 2. Multi-agent debate
        debate = self._run_debate(event, session.twin.current)

        # 3. Build execution request
        req = ExecutionRequest(
            user_id              = event.user_id,
            action_type          = self._position_to_action(debate.winning_position),
            description          = debate.final_recommendation,
            confidence           = debate.final_confidence,
            triggered_by_event   = event.event_type.value,
            agent_recommendation = debate.final_recommendation,
        )

        # 4. Policy check (PrivateVault governance gate)
        profile = {
            "consent_level":      "read_only",
            "risk_score":         session.twin.current.risk_score,
            "liquid_assets_inr":  session.twin.current.total_liquid_inr,
            "total_assets_inr":   session.twin.current.total_assets_inr,
            "monthly_expenses_inr": (
                session.twin.current.monthly_income_inr * 0.5
            ),
        }
        decision = self.policy_engine.evaluate(req, profile)

        # 5. Write to Merkle audit ledger
        entry = self.audit_ledger.record(
            decision, event.user_id, req.action_type.value
        )

        # 6. Update session stats
        session.events_processed += 1
        if decision.result == PolicyResult.ALLOWED:
            req.status = ExecutionStatus.PENDING_APPROVAL
            session.actions_executed += 1
        else:
            req.status = ExecutionStatus.BLOCKED
            session.actions_blocked += 1

        return {
            "status":          "processed",
            "event":           event.event_type.value,
            "debate_verdict":  debate.verdict.value,
            "recommendation":  debate.final_recommendation,
            "policy_result":   decision.result.value,
            "violations":      [v.value for v in decision.violations],
            "flags":           decision.flags,
            "ledger_entry":    entry.entry_hash[:12],
            "merkle_root":     (
                self.audit_ledger.merkle_root[:16]
                if self.audit_ledger.merkle_root else None
            ),
            "requires_approval": debate.requires_user_approval,
        }

    def generate_advisor_brief(
        self, advisor_id: str, client_ids: list[str]
    ) -> AdvisorBrief:
        brief = AdvisorBrief(
            advisor_id    = advisor_id,
            audit_summary = self.audit_ledger.summary(),
        )
        for cid in client_ids:
            session = self._sessions.get(cid)
            if not session:
                continue
            twin = session.twin.current
            monthly_exp = twin.monthly_income_inr * 0.5
            emergency   = monthly_exp * 6

            if twin.total_liquid_inr < emergency:
                brief.alerts.append(ClientAlert(
                    client_id            = cid,
                    client_name          = cid,
                    alert_type           = "LIQUIDITY_RISK",
                    priority             = AlertPriority.P0,
                    summary              = (
                        f"Liquid ₹{twin.total_liquid_inr:,.0f} "
                        f"< emergency fund ₹{emergency:,.0f}"
                    ),
                    recommended_action   = "Redirect next bonus to liquid FD",
                    amount_at_stake_inr  = emergency - twin.total_liquid_inr,
                ))

            brief.portfolio_drifts.append({
                "client_id":      cid,
                "net_worth_inr":  twin.net_worth_inr,
                "snapshots":      len(session.twin.history),
            })
        return brief

    def _run_debate(
        self, event: FinancialEvent, snap: TwinSnapshot
    ) -> DebateOutcome:
        args = [
            AgentArgument(
                agent_name         = "risk_agent",
                position           = AgentPosition.ALERT_ONLY,
                reasoning          = (
                    f"Event {event.event_type} requires risk re-assessment"
                ),
                confidence         = 0.85,
                recommended_action = (
                    f"Review risk after {event.event_type.value}"
                ),
                priority           = 1,
            )
        ]
        return self.debate_engine.arbitrate(
            args, event.event_type.value, event.user_id
        )

    def _position_to_action(
        self, position: Optional[AgentPosition]
    ) -> ActionType:
        from lumina.packages.autonomous_agents.agent_debate import AgentPosition
        mapping = {
            AgentPosition.REBALANCE:   ActionType.REBALANCE,
            AgentPosition.BUY:         ActionType.SIP_ADJUST,
            AgentPosition.STRONG_BUY:  ActionType.SIP_ADJUST,
            AgentPosition.ALERT_ONLY:  ActionType.ALERT_ADVISOR,
            AgentPosition.HOLD:        ActionType.ALERT_ADVISOR,
            AgentPosition.REDUCE:      ActionType.REBALANCE,
        }
        return mapping.get(position, ActionType.ALERT_ADVISOR)

    @property
    def audit_summary(self) -> dict:
        return self.audit_ledger.summary()
