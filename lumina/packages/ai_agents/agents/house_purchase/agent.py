"""
LUMINA House Purchase Agent
────────────────────────────
Answers: "Can I afford this property, and on what terms?"

Reasoning chain:
  1. Load user financial profile from wealth graph
  2. Calculate maximum loan eligibility (RBI 75/80% LTV norm)
  3. Run EMI stress test at +200bps rate shock
  4. Check down-payment gap vs liquid assets (tiered haircut model)
  5. Return structured affordability verdict + action steps
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from lumina.packages.ai_agents.core.base_agent import (
    AgentInput, AgentOutput, AgentStatus, ConsentLevel, LuminaBaseAgent,
)
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph


class HousePurchaseInput(AgentInput):
    property_value_inr: float
    loan_tenure_years: int = 20
    expected_rate_pct: float = 8.5


class HousePurchaseOutput(AgentOutput):
    max_loan_eligibility_inr: Optional[float] = None
    recommended_loan_inr: Optional[float] = None
    monthly_emi_inr: Optional[float] = None
    down_payment_gap_inr: Optional[float] = None
    stress_emi_inr: Optional[float] = None
    verdict: Optional[str] = None


class HousePurchaseAgent(LuminaBaseAgent[HousePurchaseInput, HousePurchaseOutput]):

    name = "house_purchase_agent"
    version = "1.1.0"
    required_consent = ConsentLevel.READ_ONLY

    def __init__(self, graph: WealthGraph):
        self.graph = graph

    def _run(self, inp: HousePurchaseInput) -> HousePurchaseOutput:
        trace: list[str] = []
        warnings: list[str] = []

        profile = self.graph.get_profile(inp.user_id)
        if not profile:
            return HousePurchaseOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL,
                reasoning_trace=["No financial profile found in wealth graph."],
                confidence=0.0,
            )

        trace.append(f"Loaded profile: net_worth=₹{profile.net_worth_inr:,.0f}, surplus=₹{profile.monthly_surplus_inr:,.0f}/mo")

        # Max loan = 60x monthly income (RBI FOIR ~50%)
        max_loan = profile.monthly_income_inr * 60
        trace.append(f"Max loan eligibility (60x income rule): ₹{max_loan:,.0f}")

        # LTV cap: 80% of property value
        ltv_cap = inp.property_value_inr * 0.80
        recommended_loan = min(max_loan, ltv_cap)
        trace.append(f"LTV-adjusted loan cap (80%): ₹{ltv_cap:,.0f} → recommended: ₹{recommended_loan:,.0f}")

        # EMI calculation
        emi = self._calc_emi(recommended_loan, inp.expected_rate_pct, inp.loan_tenure_years)
        stress_emi = self._calc_emi(recommended_loan, inp.expected_rate_pct + 2.0, inp.loan_tenure_years)
        trace.append(f"EMI @ {inp.expected_rate_pct}%: ₹{emi:,.0f}/mo | stress +200bps: ₹{stress_emi:,.0f}/mo")

        # Tiered liquid asset model for down payment
        # Tier 1 (100%): cash, FD         — instant access
        # Tier 2 (80%):  equity, MF       — T+3, haircut for market timing
        # Tier 3 (60%):  stocks            — volatility haircut
        # Excluded:      real_estate, crypto — illiquid or speculative
        liquid_assets = sum(
            a.current_value_inr * (
                1.00 if a.asset_type in ("cash", "fd", "savings") else
                0.80 if a.asset_type in ("mutual_fund", "debt_fund", "equity") else
                0.60 if a.asset_type == "stocks" else
                0.00
            )
            for a in profile.assets
        )

        down_payment_needed = inp.property_value_inr - recommended_loan
        gap = max(0, down_payment_needed - liquid_assets)
        trace.append(f"Liquid assets (tiered): ₹{liquid_assets:,.0f} | Down payment needed: ₹{down_payment_needed:,.0f} | Gap: ₹{gap:,.0f}")

        # Verdict
        foir = emi / profile.monthly_income_inr
        stress_foir = stress_emi / profile.monthly_income_inr

        if foir <= 0.40 and gap == 0 and stress_foir <= 0.50:
            verdict = "AFFORDABLE"
            confidence = 0.92
        elif foir <= 0.50 and gap < profile.monthly_income_inr * 6:
            verdict = "STRETCH"
            confidence = 0.65
            warnings.append(f"FOIR is {foir:.0%} — above comfortable 40% threshold.")
        else:
            verdict = "NOT_ADVISED"
            confidence = 0.85
            warnings.append("EMI exceeds 50% of income or down-payment gap too large.")

        trace.append(f"Verdict: {verdict} (FOIR={foir:.0%}, stress_FOIR={stress_foir:.0%})")

        return HousePurchaseOutput(
            session_id=inp.session_id, agent_name=self.name,
            status=AgentStatus.SUCCESS,
            reasoning_trace=trace,
            warnings=warnings,
            confidence=confidence,
            max_loan_eligibility_inr=max_loan,
            recommended_loan_inr=recommended_loan,
            monthly_emi_inr=emi,
            down_payment_gap_inr=gap,
            stress_emi_inr=stress_emi,
            verdict=verdict,
        )

    @staticmethod
    def _calc_emi(principal: float, annual_rate_pct: float, years: int) -> float:
        r = (annual_rate_pct / 100) / 12
        n = years * 12
        if r == 0:
            return principal / n
        return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
