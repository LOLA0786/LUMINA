"""
LUMINA Tax Agent
────────────────
Answers: "How much tax will I pay this year, and how can I reduce it?"

Covers Indian tax regime (FY 2024-25):
  - Old vs New regime comparison
  - 80C, 80D, HRA, NPS deductions
  - LTCG / STCG from equity and debt
"""

from __future__ import annotations

from lumina.packages.ai_agents.core.base_agent import (
    AgentInput, AgentOutput, AgentStatus, ConsentLevel, LuminaBaseAgent,
)
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph


class TaxInput(AgentInput):
    deductions_80c_inr: float = 0
    deductions_80d_inr: float = 0
    hra_exemption_inr: float = 0
    nps_80ccd_inr: float = 0
    ltcg_inr: float = 0        # Long-term capital gains
    stcg_inr: float = 0        # Short-term capital gains


class TaxOutput(AgentOutput):
    old_regime_tax_inr: float = 0
    new_regime_tax_inr: float = 0
    recommended_regime: str = ""
    tax_savings_possible_inr: float = 0
    optimization_tips: list[str] = []


class TaxAgent(LuminaBaseAgent[TaxInput, TaxOutput]):

    name = "tax_agent"
    version = "1.0.0"
    required_consent = ConsentLevel.READ_ONLY

    def __init__(self, graph: WealthGraph):
        self.graph = graph

    def _run(self, inp: TaxInput) -> TaxOutput:
        trace: list[str] = []
        tips: list[str] = []

        profile = self.graph.get_profile(inp.user_id)
        if not profile:
            return TaxOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL, confidence=0.0,
                reasoning_trace=["Profile not found."],
            )

        annual_income = profile.monthly_income_inr * 12
        trace.append(f"Annual income: ₹{annual_income:,.0f}")

        # Old regime
        total_deductions = min(150000, inp.deductions_80c_inr) + inp.deductions_80d_inr + inp.hra_exemption_inr + min(50000, inp.nps_80ccd_inr)
        old_taxable = max(0, annual_income - total_deductions - 50000)  # std deduction
        old_tax = self._slab_tax_old(old_taxable)

        # New regime (FY24-25 slabs)
        new_taxable = max(0, annual_income - 75000)  # standard deduction new regime
        new_tax = self._slab_tax_new(new_taxable)

        # Capital gains
        ltcg_tax = max(0, inp.ltcg_inr - 125000) * 0.10
        stcg_tax = inp.stcg_inr * 0.15

        old_total = old_tax + ltcg_tax + stcg_tax
        new_total = new_tax + ltcg_tax + stcg_tax

        trace.append(f"Old regime tax: ₹{old_total:,.0f} | New regime tax: ₹{new_total:,.0f}")

        recommended = "OLD" if old_total < new_total else "NEW"
        savings = abs(old_total - new_total)

        # Tips
        if inp.deductions_80c_inr < 150000:
            gap = 150000 - inp.deductions_80c_inr
            tips.append(f"Invest ₹{gap:,.0f} more in 80C instruments (ELSS/PPF) to maximise deduction.")
        if inp.deductions_80d_inr < 25000:
            tips.append("Health insurance premium up to ₹25,000 qualifies under 80D.")
        if inp.nps_80ccd_inr < 50000:
            tips.append("Contribute to NPS for additional ₹50,000 deduction under 80CCD(1B).")

        return TaxOutput(
            session_id=inp.session_id, agent_name=self.name,
            status=AgentStatus.SUCCESS,
            reasoning_trace=trace,
            confidence=0.90,
            old_regime_tax_inr=old_total,
            new_regime_tax_inr=new_total,
            recommended_regime=recommended,
            tax_savings_possible_inr=savings,
            optimization_tips=tips,
        )

    @staticmethod
    def _slab_tax_old(income: float) -> float:
        slabs = [(250000, 0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)]
        tax, prev = 0.0, 0.0
        for limit, rate in slabs:
            if income <= prev:
                break
            taxable = min(income, limit) - prev
            tax += taxable * rate
            prev = limit
        return tax * 1.04  # 4% cess

    @staticmethod
    def _slab_tax_new(income: float) -> float:
        slabs = [(300000, 0), (700000, 0.05), (1000000, 0.10), (1200000, 0.15), (1500000, 0.20), (float("inf"), 0.30)]
        tax, prev = 0.0, 0.0
        for limit, rate in slabs:
            if income <= prev:
                break
            taxable = min(income, limit) - prev
            tax += taxable * rate
            prev = limit
        return tax * 1.04
