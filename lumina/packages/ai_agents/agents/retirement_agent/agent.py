"""
LUMINA Retirement Agent
────────────────────────
Answers: "Am I on track to retire, and when can I retire comfortably?"

Reasoning chain:
  1. Project corpus at retirement age via SIP + existing investments
  2. Calculate sustainable withdrawal (4% SWR rule + India inflation adj.)
  3. Check if corpus sustains target monthly spend until life expectancy
  4. Compute shortfall or surplus
"""

from __future__ import annotations

from lumina.packages.ai_agents.core.base_agent import (
    AgentInput, AgentOutput, AgentStatus, ConsentLevel, LuminaBaseAgent,
)
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph


class RetirementInput(AgentInput):
    target_retirement_age: int = 60
    life_expectancy: int = 85
    desired_monthly_spend_inr: float = 100000
    expected_annual_return_pct: float = 10.0
    inflation_pct: float = 6.0
    monthly_sip_inr: float = 0


class RetirementOutput(AgentOutput):
    projected_corpus_inr: float = 0
    required_corpus_inr: float = 0
    surplus_or_shortfall_inr: float = 0
    on_track: bool = False
    years_to_retirement: int = 0
    recommended_monthly_sip_inr: float = 0


class RetirementAgent(LuminaBaseAgent[RetirementInput, RetirementOutput]):

    name = "retirement_agent"
    version = "1.0.0"
    required_consent = ConsentLevel.READ_ONLY

    def __init__(self, graph: WealthGraph):
        self.graph = graph

    def _run(self, inp: RetirementInput) -> RetirementOutput:
        trace: list[str] = []

        profile = self.graph.get_profile(inp.user_id)
        if not profile:
            return RetirementOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL, confidence=0.0,
                reasoning_trace=["Profile not found."],
            )

        years_left = inp.target_retirement_age - profile.age
        if years_left <= 0:
            return RetirementOutput(
                session_id=inp.session_id, agent_name=self.name,
                status=AgentStatus.PARTIAL, confidence=0.5,
                reasoning_trace=["Already at or past retirement age."],
            )

        r = inp.expected_annual_return_pct / 100
        inf = inp.inflation_pct / 100

        # Future value of existing portfolio
        existing_fv = profile.net_worth_inr * (1 + r) ** years_left
        trace.append(f"FV of existing net worth ₹{profile.net_worth_inr:,.0f} → ₹{existing_fv:,.0f}")

        # Future value of SIP
        monthly_r = r / 12
        months = years_left * 12
        sip_fv = inp.monthly_sip_inr * (((1 + monthly_r) ** months - 1) / monthly_r) * (1 + monthly_r)
        trace.append(f"FV of ₹{inp.monthly_sip_inr:,.0f}/mo SIP over {years_left}yrs → ₹{sip_fv:,.0f}")

        projected = existing_fv + sip_fv

        # Required corpus: inflation-adjusted spend for retirement years
        # real rate of return during retirement
        retirement_years = inp.life_expectancy - inp.target_retirement_age
        real_r = (1 + r) / (1 + inf) - 1
        inflation_adj_spend = inp.desired_monthly_spend_inr * (1 + inf) ** years_left * 12
        if real_r > 0:
            required = inflation_adj_spend * (1 - (1 + real_r) ** (-retirement_years)) / real_r
        else:
            required = inflation_adj_spend * retirement_years

        trace.append(f"Required corpus (inflation-adj): ₹{required:,.0f}")
        trace.append(f"Projected corpus: ₹{projected:,.0f}")

        gap = projected - required

        # Recommended SIP to close gap
        if gap < 0:
            additional_needed = -gap
            rec_sip = additional_needed / (((1 + monthly_r) ** months - 1) / monthly_r * (1 + monthly_r))
        else:
            rec_sip = inp.monthly_sip_inr

        return RetirementOutput(
            session_id=inp.session_id, agent_name=self.name,
            status=AgentStatus.SUCCESS,
            reasoning_trace=trace,
            confidence=0.87,
            projected_corpus_inr=projected,
            required_corpus_inr=required,
            surplus_or_shortfall_inr=gap,
            on_track=gap >= 0,
            years_to_retirement=years_left,
            recommended_monthly_sip_inr=max(rec_sip, inp.monthly_sip_inr),
        )
