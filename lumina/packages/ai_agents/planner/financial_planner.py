"""
LUMINA Master Financial Planner
─────────────────────────────────
The orchestration layer.

Given a user query in plain English, the planner:
  1. Selects which agents to invoke (and in what order)
  2. Passes session memory between agents
  3. Synthesises a unified financial brief

This is LUMINA's core reasoning engine — the thing no
vibe-coder can replicate, because it encodes financial
domain logic + safe reasoning architecture together.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from lumina.packages.ai_agents.agents.house_purchase.agent import HousePurchaseAgent, HousePurchaseInput
from lumina.packages.ai_agents.agents.portfolio_agent.agent import PortfolioAgent, PortfolioInput
from lumina.packages.ai_agents.agents.retirement_agent.agent import RetirementAgent, RetirementInput
from lumina.packages.ai_agents.agents.risk_agent.agent import RiskAgent, RiskInput
from lumina.packages.ai_agents.agents.tax_agent.agent import TaxAgent, TaxInput
from lumina.packages.ai_agents.core.base_agent import AgentInput, ConsentLevel
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph
from lumina.packages.ai_agents.memory.session_memory import SessionMemory

logger = logging.getLogger("lumina.planner")


class PlannerIntent(str, Enum):
    FULL_REVIEW = "full_review"
    HOUSE_PURCHASE = "house_purchase"
    PORTFOLIO = "portfolio"
    TAX = "tax"
    RETIREMENT = "retirement"
    RISK = "risk"


@dataclass
class PlannerRequest:
    user_id: str
    intent: PlannerIntent
    consent_level: ConsentLevel = ConsentLevel.READ_ONLY
    params: dict = None  # intent-specific params

    def __post_init__(self):
        if self.params is None:
            self.params = {}


@dataclass
class PlannerResponse:
    user_id: str
    intent: str
    agent_results: dict
    memory_snapshot: dict
    overall_health_score: Optional[float] = None
    executive_summary: str = ""


class FinancialPlanner:
    """
    The brain of LUMINA.
    Add new agents here — planner automatically composes them.
    """

    def __init__(self, graph: WealthGraph):
        self.graph = graph
        self.agents = {
            "house_purchase": HousePurchaseAgent(graph),
            "portfolio": PortfolioAgent(graph),
            "tax": TaxAgent(graph),
            "retirement": RetirementAgent(graph),
            "risk": RiskAgent(graph),
        }

    def run(self, request: PlannerRequest) -> PlannerResponse:
        memory = SessionMemory()
        results = {}
        base = {"user_id": request.user_id, "consent_level": request.consent_level}

        if request.intent in (PlannerIntent.FULL_REVIEW, PlannerIntent.RISK):
            out = self.agents["risk"](RiskInput(**base, **request.params))
            results["risk"] = out.dict()
            memory.write("risk_agent", "overall_risk_score", out.overall_risk_score)
            memory.write("risk_agent", "risk_flags", out.risk_flags)

        if request.intent in (PlannerIntent.FULL_REVIEW, PlannerIntent.PORTFOLIO):
            out = self.agents["portfolio"](PortfolioInput(**base))
            results["portfolio"] = out.dict()
            memory.write("portfolio_agent", "rebalance_actions", out.rebalance_actions)

        if request.intent in (PlannerIntent.FULL_REVIEW, PlannerIntent.TAX):
            out = self.agents["tax"](TaxInput(**base, **request.params))
            results["tax"] = out.dict()
            memory.write("tax_agent", "recommended_regime", out.recommended_regime)
            memory.write("tax_agent", "tax_savings_possible", out.tax_savings_possible_inr)

        if request.intent in (PlannerIntent.FULL_REVIEW, PlannerIntent.RETIREMENT):
            out = self.agents["retirement"](RetirementInput(**base, **request.params))
            results["retirement"] = out.dict()
            memory.write("retirement_agent", "on_track", out.on_track)

        if request.intent == PlannerIntent.HOUSE_PURCHASE:
            out = self.agents["house_purchase"](HousePurchaseInput(**base, **request.params))
            results["house_purchase"] = out.dict()

        # Health score (simple composite from available agent outputs)
        health_inputs = []
        if "risk" in results:
            risk_score = results["risk"].get("overall_risk_score", 0.5)
            health_inputs.append(1 - risk_score)
        if "retirement" in results:
            health_inputs.append(1.0 if results["retirement"].get("on_track") else 0.4)
        if "portfolio" in results:
            health_inputs.append(0.9 if not results["portfolio"].get("rebalance_actions") else 0.6)

        health = sum(health_inputs) / len(health_inputs) if health_inputs else None

        summary = self._build_summary(results, health)
        logger.info("[Planner] user=%s intent=%s health=%.2f", request.user_id, request.intent, health or 0)

        return PlannerResponse(
            user_id=request.user_id,
            intent=request.intent,
            agent_results=results,
            memory_snapshot=memory.snapshot(),
            overall_health_score=health,
            executive_summary=summary,
        )

    def _build_summary(self, results: dict, health: Optional[float]) -> str:
        parts = []
        if health is not None:
            grade = "Excellent" if health > 0.8 else "Good" if health > 0.6 else "Needs Attention"
            parts.append(f"Financial Health: {grade} ({health:.0%})")
        if "risk" in results and results["risk"].get("risk_flags"):
            parts.append(f"Risk Flags: {len(results['risk']['risk_flags'])} active")
        if "retirement" in results:
            on_track = results["retirement"].get("on_track")
            parts.append(f"Retirement: {'On Track ✓' if on_track else 'Behind — SIP adjustment needed'}")
        if "tax" in results:
            regime = results["tax"].get("recommended_regime", "")
            savings = results["tax"].get("tax_savings_possible_inr", 0)
            parts.append(f"Tax: Use {regime} regime | Potential saving ₹{savings:,.0f}")
        return " | ".join(parts) if parts else "Analysis complete."
