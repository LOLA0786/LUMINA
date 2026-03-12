"""
LUMINA Portfolio Agent
────────────────────────
Answers: "Is my portfolio optimally allocated for my goals and risk?"

Reasoning chain:
  1. Compute current asset allocation
  2. Derive target allocation from risk score + age (100-age rule adjusted)
  3. Calculate drift from target
  4. Recommend rebalancing actions
"""

from __future__ import annotations

from typing import Optional

from lumina.packages.ai_agents.core.base_agent import (
    AgentInput, AgentOutput, AgentStatus, ConsentLevel, LuminaBaseAgent,
)
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph


class PortfolioInput(AgentInput):
    rebalance_threshold_pct: float = 5.0   # trigger rebalance if drift > this


class PortfolioOutput(AgentOutput):
    current_allocation: Optional[dict[str, float]] = None
    target_allocation: Optional[dict[str, float]] = None
    drift: Optional[dict[str, float]] = None
    rebalance_actions: list[str] = []
    total_portfolio_inr: Optional[float] = None


class PortfolioAgent(LuminaBaseAgent[PortfolioInput, PortfolioOutput]):

    name = "portfolio_agent"
    version = "1.0.0"
    required_consent = ConsentLevel.READ_ONLY

    def __init__(self, graph: WealthGraph):
        self.graph = graph

    def _run(self, inp: PortfolioInput) -> PortfolioOutput:
        trace: list[str] = []
        profile = self.graph.get_profile(inp.user_id)
        if not profile:
            return PortfolioOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL, confidence=0.0,
                reasoning_trace=["Profile not found."],
            )

        total = sum(a.current_value_inr for a in profile.assets)
        if total == 0:
            return PortfolioOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL, confidence=0.1,
                reasoning_trace=["No assets found in portfolio."],
            )

        # Current allocation
        current: dict[str, float] = {}
        for asset in profile.assets:
            t = asset.asset_type
            current[t] = current.get(t, 0) + (asset.current_value_inr / total * 100)

        trace.append(f"Total portfolio: ₹{total:,.0f}")
        trace.append(f"Current allocation: {current}")

        # Target allocation (age-adjusted, risk-weighted)
        equity_target = min(80, max(20, (100 - profile.age) * (0.5 + profile.risk_score * 0.5)))
        target = {
            "equity": equity_target,
            "real_estate": 20.0,
            "cash": max(5, 100 - equity_target - 20 - 5),
            "other": 5.0,
        }
        trace.append(f"Target allocation (age={profile.age}, risk={profile.risk_score:.1f}): {target}")

        # Drift
        all_types = set(list(current.keys()) + list(target.keys()))
        drift = {k: current.get(k, 0) - target.get(k, 0) for k in all_types}

        # Actions
        actions = []
        for k, d in drift.items():
            if abs(d) >= inp.rebalance_threshold_pct:
                direction = "REDUCE" if d > 0 else "INCREASE"
                actions.append(f"{direction} {k} by {abs(d):.1f}% (≈₹{abs(d)/100*total:,.0f})")

        trace.append(f"Rebalance actions needed: {len(actions)}")

        return PortfolioOutput(
            session_id=inp.session_id, agent_name=self.name,
            status=AgentStatus.SUCCESS,
            reasoning_trace=trace,
            confidence=0.88,
            current_allocation=current,
            target_allocation=target,
            drift=drift,
            rebalance_actions=actions,
            total_portfolio_inr=total,
        )
