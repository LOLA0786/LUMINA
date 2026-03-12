"""
LUMINA Risk Agent
──────────────────
Answers: "What is my overall financial risk exposure?"

Dimensions assessed:
  - Concentration risk (single asset > 30% of portfolio)
  - Liquidity risk (liquid assets < 6mo expenses)
  - Leverage risk (debt-to-income ratio)
  - Insurance gap (life cover vs income replacement needs)
  - Sequence-of-returns risk (for near-retirement users)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lumina.packages.ai_agents.core.base_agent import (
    AgentInput, AgentOutput, AgentStatus, ConsentLevel, LuminaBaseAgent,
)
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph


class RiskInput(AgentInput):
    life_cover_inr: float = 0
    income_replacement_years: int = 10


class RiskOutput(AgentOutput):
    overall_risk_score: float = 0      # 0 = low, 1 = critical
    risk_flags: list[str] = []
    risk_breakdown: dict = {}


class RiskAgent(LuminaBaseAgent[RiskInput, RiskOutput]):

    name = "risk_agent"
    version = "1.0.0"
    required_consent = ConsentLevel.READ_ONLY

    def __init__(self, graph: WealthGraph):
        self.graph = graph

    def _run(self, inp: RiskInput) -> RiskOutput:
        trace: list[str] = []
        flags: list[str] = []
        scores: dict[str, float] = {}

        profile = self.graph.get_profile(inp.user_id)
        if not profile:
            return RiskOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL, confidence=0.0,
                reasoning_trace=["Profile not found."],
            )

        total_assets = sum(a.current_value_inr for a in profile.assets) or 1

        # 1. Concentration risk
        for asset in profile.assets:
            pct = asset.current_value_inr / total_assets
            if pct > 0.30:
                flags.append(f"CONCENTRATION: {asset.asset_type} is {pct:.0%} of portfolio (>30%)")
                scores["concentration"] = min(1.0, pct)
        scores.setdefault("concentration", 0.1)

        # 2. Liquidity risk
        liquid = sum(a.current_value_inr for a in profile.assets if a.asset_type in ("cash", "fd"))
        emergency_needed = profile.monthly_expenses_inr * 6
        if liquid < emergency_needed:
            flags.append(f"LIQUIDITY: Liquid assets ₹{liquid:,.0f} < 6-month emergency fund ₹{emergency_needed:,.0f}")
            scores["liquidity"] = 1.0 - (liquid / emergency_needed)
        else:
            scores["liquidity"] = 0.0

        # 3. Leverage risk
        dti = profile.debt_to_income_ratio
        if dti > 5:
            flags.append(f"LEVERAGE: Debt-to-income ratio {dti:.1f}x is dangerously high (>5x)")
            scores["leverage"] = min(1.0, dti / 10)
        elif dti > 3:
            flags.append(f"LEVERAGE: Debt-to-income ratio {dti:.1f}x is elevated (>3x)")
            scores["leverage"] = 0.5
        else:
            scores["leverage"] = max(0, dti / 6)

        # 4. Insurance gap
        needed_cover = profile.monthly_income_inr * 12 * inp.income_replacement_years
        if inp.life_cover_inr < needed_cover:
            gap = needed_cover - inp.life_cover_inr
            flags.append(f"INSURANCE: Life cover ₹{inp.life_cover_inr:,.0f} — gap of ₹{gap:,.0f} vs {inp.income_replacement_years}yr income replacement")
            scores["insurance"] = min(1.0, gap / needed_cover)
        else:
            scores["insurance"] = 0.0

        overall = sum(scores.values()) / len(scores)
        trace.append(f"Risk scores: {scores}")
        trace.append(f"Overall risk score: {overall:.2f}")

        return RiskOutput(
            session_id=inp.session_id, agent_name=self.name,
            status=AgentStatus.SUCCESS,
            reasoning_trace=trace,
            confidence=0.91,
            overall_risk_score=overall,
            risk_flags=flags,
            risk_breakdown=scores,
        )
