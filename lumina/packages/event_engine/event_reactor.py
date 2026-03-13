"""
LUMINA Event Reactor
════════════════════
Closes the loop:
  event → agent → decision → audit log

Before this file:
  EventBus fired events but handlers=0
  Agents ran separately in batch
  No automatic connection between the two

After this file:
  salary_credited  → tax_agent + retirement_agent + risk_agent run immediately
  market_crash     → portfolio_agent + risk_agent run immediately
  goal_at_risk     → retirement_agent runs immediately
  loan_closed      → portfolio_agent + retirement_agent run immediately

Every agent response goes straight to the debate engine,
then to governance, then to the audit ledger.
One event. Full pipeline. Automatic.
"""
from __future__ import annotations

import time
from typing import Any

from lumina.packages.event_engine.event_bus import EventBus, DEFAULT_ROUTING
from lumina.packages.event_engine.financial_events import (
    EventType, FinancialEvent,
)
from lumina.observability.logging import get_logger

logger = get_logger("lumina.event_reactor")


class EventReactor:
    """
    Wires the EventBus to the agent suite.
    Subscribes one handler per event type.
    Each handler runs the relevant agents immediately.
    """

    def __init__(self, financial_os):
        self._os = financial_os
        self._wired = False

    def wire(self) -> None:
        """
        Subscribe reactive handlers to every event type
        that has a known agent routing.
        Call once at OS startup.
        """
        if self._wired:
            return

        for event_type, agent_names in DEFAULT_ROUTING.items():
            # Capture agent_names in closure correctly
            def make_handler(agents: list[str]):
                def handler(event: FinancialEvent) -> None:
                    self._react(event, agents)
                handler.__name__ = f"reactor_{event_type.value}"
                return handler

            self._os.event_bus.subscribe(event_type, make_handler(agent_names))
            logger.info(
                "reactor.wired",
                event_type = event_type.value,
                agents     = agent_names,
            )

        self._wired = True
        logger.info("reactor.ready", routes=len(DEFAULT_ROUTING))

    def _react(self, event: FinancialEvent, agent_names: list[str]) -> None:
        """
        Immediate agent reaction to an event.
        Runs relevant agents, collects arguments,
        debates, checks governance, writes to ledger.
        """
        session = self._os._sessions.get(event.user_id)
        if not session:
            logger.info(
                "reactor.skip",
                reason   = "user_not_in_session",
                user_id  = event.user_id,
            )
            return

        snap = session.twin.current
        start = time.perf_counter()

        logger.info(
            "reactor.reacting",
            event_type = event.event_type.value,
            user_id    = event.user_id,
            agents     = agent_names,
        )

        # Build agent arguments from each relevant agent
        from lumina.packages.autonomous_agents.agent_debate import (
            AgentArgument, AgentPosition,
        )

        arguments = []
        for agent_name in agent_names:
            arg = self._run_agent(agent_name, event, snap)
            if arg:
                arguments.append(arg)

        if not arguments:
            return

        # Debate
        debate = self._os.debate_engine.arbitrate(
            arguments,
            event.event_type.value,
            event.user_id,
        )

        # Governance + audit
        from lumina.packages.execution_layer.execution_request import ExecutionRequest
        req = ExecutionRequest(
            user_id              = event.user_id,
            action_type          = self._os._position_to_action(
                debate.winning_position
            ),
            description          = debate.final_recommendation,
            confidence           = debate.final_confidence,
            triggered_by_event   = event.event_type.value,
            agent_recommendation = debate.final_recommendation,
        )

        profile = {
            "consent_level":        "read_only",
            "risk_score":           snap.risk_score,
            "liquid_assets_inr":    snap.total_liquid_inr,
            "total_assets_inr":     snap.total_assets_inr,
            "monthly_expenses_inr": snap.monthly_income_inr * 0.5,
        }

        decision = self._os.policy_engine.evaluate(req, profile)
        entry    = self._os.audit_ledger.record(
            decision, event.user_id, req.action_type.value
        )

        latency = (time.perf_counter() - start) * 1000
        logger.info(
            "reactor.complete",
            event_type     = event.event_type.value,
            user_id        = event.user_id,
            agents_ran     = len(arguments),
            verdict        = debate.verdict.value,
            policy_result  = decision.result.value,
            latency_ms     = round(latency, 2),
            merkle_entry   = entry.entry_hash[:12],
        )

    def _run_agent(
        self,
        agent_name: str,
        event: FinancialEvent,
        snap: Any,
    ):
        """
        Map agent name → position based on event type + twin state.
        In production: calls real agent._run() with full WealthGraph.
        Here: produces a typed AgentArgument with financial reasoning.
        """
        from lumina.packages.autonomous_agents.agent_debate import (
            AgentArgument, AgentPosition,
        )
        from lumina.packages.event_engine.financial_events import EventType

        et = event.event_type

        # Risk agent
        if agent_name == "risk_agent":
            monthly_exp    = snap.monthly_income_inr * 0.5
            emergency_fund = monthly_exp * 6
            liquid         = snap.total_liquid_inr
            if liquid < emergency_fund:
                return AgentArgument(
                    agent_name         = "risk_agent",
                    position           = AgentPosition.ALERT_ONLY,
                    reasoning          = (
                        f"Liquidity ₹{liquid:,.0f} below "
                        f"emergency fund ₹{emergency_fund:,.0f}"
                    ),
                    confidence         = 0.92,
                    recommended_action = "Build emergency fund before investing",
                    priority           = 1,
                )
            return AgentArgument(
                agent_name         = "risk_agent",
                position           = AgentPosition.HOLD,
                reasoning          = "Liquidity adequate. Monitor event impact.",
                confidence         = 0.80,
                recommended_action = f"Monitor after {et.value}",
                priority           = 1,
            )

        # Portfolio agent
        if agent_name == "portfolio_agent":
            if et == EventType.MARKET_CRASH:
                drawdown = event.payload.get("drawdown_pct", 10)
                if drawdown > 15:
                    return AgentArgument(
                        agent_name         = "portfolio_agent",
                        position           = AgentPosition.BUY,
                        reasoning          = (
                            f"Market down {drawdown}% — buying opportunity "
                            "for long-horizon investor"
                        ),
                        confidence         = 0.75,
                        recommended_action = "Step-up SIP by 25% for 3 months",
                        priority           = 3,
                    )
                return AgentArgument(
                    agent_name         = "portfolio_agent",
                    position           = AgentPosition.HOLD,
                    reasoning          = f"Drawdown {drawdown}% manageable. Hold.",
                    confidence         = 0.82,
                    recommended_action = "No action needed",
                    priority           = 3,
                )
            if et in (EventType.SALARY_CREDITED, EventType.BONUS_RECEIVED):
                amount = event.payload.get("amount_inr", 0)
                return AgentArgument(
                    agent_name         = "portfolio_agent",
                    position           = AgentPosition.BUY,
                    reasoning          = (
                        f"₹{amount:,.0f} income received — "
                        "route surplus to equity SIP"
                    ),
                    confidence         = 0.78,
                    recommended_action = "Increase SIP by 10% of net increment",
                    priority           = 3,
                )
            return AgentArgument(
                agent_name         = "portfolio_agent",
                position           = AgentPosition.HOLD,
                reasoning          = "No portfolio action needed for this event",
                confidence         = 0.70,
                priority           = 3,
            )

        # Retirement agent
        if agent_name == "retirement_agent":
            if et == EventType.GOAL_AT_RISK:
                shortfall = event.payload.get("shortfall_inr", 0)
                return AgentArgument(
                    agent_name         = "retirement_agent",
                    position           = AgentPosition.STRONG_BUY,
                    reasoning          = (
                        f"Goal shortfall ₹{shortfall:,.0f} — "
                        "immediate SIP increase required"
                    ),
                    confidence         = 0.91,
                    recommended_action = (
                        f"Increase SIP to cover ₹{shortfall:,.0f} shortfall"
                    ),
                    recommended_amount_inr = shortfall / 12,
                    priority           = 2,
                )
            if et == EventType.LOAN_CLOSED:
                freed = event.payload.get("freed_emi_inr", 0)
                return AgentArgument(
                    agent_name         = "retirement_agent",
                    position           = AgentPosition.BUY,
                    reasoning          = (
                        f"Loan closed — redirect freed EMI "
                        f"₹{freed:,.0f} to retirement SIP"
                    ),
                    confidence         = 0.88,
                    recommended_action = (
                        f"Add ₹{freed:,.0f}/mo to retirement SIP"
                    ),
                    recommended_amount_inr = freed,
                    priority           = 2,
                )
            return AgentArgument(
                agent_name         = "retirement_agent",
                position           = AgentPosition.HOLD,
                reasoning          = "Retirement trajectory unchanged",
                confidence         = 0.72,
                priority           = 2,
            )

        # Tax agent
        if agent_name == "tax_agent":
            if et in (EventType.SALARY_CREDITED, EventType.BONUS_RECEIVED):
                amount = event.payload.get("amount_inr", 0)
                return AgentArgument(
                    agent_name         = "tax_agent",
                    position           = AgentPosition.ALERT_ONLY,
                    reasoning          = (
                        f"₹{amount:,.0f} income — "
                        "verify TDS and advance tax position"
                    ),
                    confidence         = 0.85,
                    recommended_action = "Check Form 26AS after credit",
                    priority           = 4,
                )
            if et == EventType.TAX_LAW_CHANGE:
                return AgentArgument(
                    agent_name         = "tax_agent",
                    position           = AgentPosition.ALERT_ONLY,
                    reasoning          = "Tax law changed — regime re-evaluation needed",
                    confidence         = 0.95,
                    recommended_action = "Re-run old vs new regime comparison",
                    priority           = 4,
                )
            return AgentArgument(
                agent_name         = "tax_agent",
                position           = AgentPosition.HOLD,
                reasoning          = "No tax action needed",
                confidence         = 0.70,
                priority           = 4,
            )

        return None
