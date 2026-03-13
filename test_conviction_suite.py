"""
LUMINA — Institutional Conviction Test Suite
═════════════════════════════════════════════
Written from the perspective of a wealth management firm
evaluating LUMINA before deploying to HNI clients.

These are not unit tests.
These are CONVICTION tests.

Each test encodes a real scenario a relationship manager
would face. If LUMINA gets these right, it earns the room.

Run: python -m pytest test_conviction_suite.py -v --tb=short
"""

import pytest

from lumina.packages.ai_agents.agents.house_purchase.agent import (
    HousePurchaseAgent, HousePurchaseInput,
)
from lumina.packages.ai_agents.agents.portfolio_agent.agent import (
    PortfolioAgent, PortfolioInput,
)
from lumina.packages.ai_agents.agents.retirement_agent.agent import (
    RetirementAgent, RetirementInput,
)
from lumina.packages.ai_agents.agents.risk_agent.agent import (
    RiskAgent, RiskInput,
)
from lumina.packages.ai_agents.agents.tax_agent.agent import (
    TaxAgent, TaxInput,
)
from lumina.packages.ai_agents.core.base_agent import AgentStatus, ConsentLevel
from lumina.packages.ai_agents.graph.wealth_graph import (
    AssetNode, LiabilityNode, UserFinancialProfile, WealthGraph,
)
from lumina.packages.ai_agents.planner.financial_planner import (
    FinancialPlanner, PlannerIntent, PlannerRequest,
)


# ══════════════════════════════════════════════════════════════
# FIXTURES — Real Indian client archetypes
# ══════════════════════════════════════════════════════════════

def make_graph(*profiles):
    g = WealthGraph()
    for p in profiles:
        g.load_fixture(p)
    return g


@pytest.fixture
def rohan():
    """
    Rohan, 34, Bangalore. Senior SDE at a startup.
    ₹2.2L/mo, no property, heavy equity, wants to buy a flat.
    Classic DINK tech professional.
    """
    return UserFinancialProfile(
        user_id="rohan",
        monthly_income_inr=220000,
        monthly_expenses_inr=90000,
        age=34,
        risk_score=0.75,
        assets=[
            AssetNode("r1", "equity", 2800000),
            AssetNode("r2", "cash", 350000),
            AssetNode("r3", "crypto", 200000),
        ],
        liabilities=[],
    )


@pytest.fixture
def sunita():
    """
    Sunita, 52, Mumbai. Partner at a CA firm.
    ₹5.5L/mo, owns 2 properties, planning retirement at 58.
    High income, high tax, under-invested in equity.
    """
    return UserFinancialProfile(
        user_id="sunita",
        monthly_income_inr=550000,
        monthly_expenses_inr=180000,
        age=52,
        risk_score=0.35,
        assets=[
            AssetNode("s1", "real_estate", 22000000),
            AssetNode("s2", "equity", 3000000),
            AssetNode("s3", "cash", 800000),
            AssetNode("s4", "fd", 2500000),
        ],
        liabilities=[
            LiabilityNode("sl1", "home_loan", 4000000, 8.75, 72),
        ],
    )


@pytest.fixture
def vikram():
    """
    Vikram, 28, Pune. First job, IT services.
    ₹65K/mo, no savings, just started.
    """
    return UserFinancialProfile(
        user_id="vikram",
        monthly_income_inr=65000,
        monthly_expenses_inr=55000,
        age=28,
        risk_score=0.80,
        assets=[
            AssetNode("v1", "cash", 45000),
        ],
        liabilities=[
            LiabilityNode("vl1", "personal_loan", 150000, 14.0, 18),
        ],
    )


@pytest.fixture
def priya():
    """
    Priya, 45, Delhi. Business owner, ₹8L/mo.
    Concentrated in real estate, almost no equity.
    """
    return UserFinancialProfile(
        user_id="priya",
        monthly_income_inr=800000,
        monthly_expenses_inr=250000,
        age=45,
        risk_score=0.50,
        assets=[
            AssetNode("p1", "real_estate", 45000000),
            AssetNode("p2", "cash", 1200000),
            AssetNode("p3", "equity", 500000),
        ],
        liabilities=[
            LiabilityNode("pl1", "home_loan", 8000000, 9.0, 144),
        ],
    )


# ══════════════════════════════════════════════════════════════
# BLOCK 1: CONSENT & SAFETY
# ══════════════════════════════════════════════════════════════

class TestConsentAndSafety:

    def test_no_consent_always_blocked(self, rohan):
        graph = make_graph(rohan)
        agent = HousePurchaseAgent(graph)

        result = agent(HousePurchaseInput(
            user_id="rohan",
            property_value_inr=10000000,
            consent_level=ConsentLevel.NONE,
        ))

        assert result.status == AgentStatus.BLOCKED


    def test_unknown_user_returns_partial_not_crash(self, rohan):
        graph = make_graph(rohan)
        agent = RiskAgent(graph)

        result = agent(RiskInput(
            user_id="does_not_exist",
            consent_level=ConsentLevel.READ_ONLY,
        ))

        assert result.status == AgentStatus.PARTIAL
        assert result.confidence == 0.0


    def test_reasoning_trace_always_present(self, rohan):
        graph = make_graph(rohan)
        agent = PortfolioAgent(graph)

        result = agent(PortfolioInput(
            user_id="rohan",
            consent_level=ConsentLevel.READ_ONLY,
        ))

        assert len(result.reasoning_trace) >= 2


    def test_confidence_score_between_0_and_1(self, sunita):
        graph = make_graph(sunita)
        agent = TaxAgent(graph)

        result = agent(TaxInput(
            user_id="sunita",
            consent_level=ConsentLevel.READ_ONLY,
            deductions_80c_inr=150000,
        ))

        assert 0.0 <= result.confidence <= 1.0


# ══════════════════════════════════════════════════════════════
# BLOCK 2: HOUSE PURCHASE
# ══════════════════════════════════════════════════════════════

class TestHousePurchase:

    def test_rohan_can_afford_1cr_flat(self, rohan):
        graph = make_graph(rohan)
        agent = HousePurchaseAgent(graph)

        result = agent(HousePurchaseInput(
            user_id="rohan",
            property_value_inr=10000000,
            consent_level=ConsentLevel.READ_ONLY,
        ))

        assert result.status == AgentStatus.SUCCESS
        assert result.verdict == "AFFORDABLE"
        assert result.monthly_emi_inr > 0
        assert result.monthly_emi_inr < rohan.monthly_income_inr * 0.45


    def test_vikram_cannot_afford_2cr_flat(self, vikram):
        graph = make_graph(vikram)
        agent = HousePurchaseAgent(graph)

        result = agent(HousePurchaseInput(
            user_id="vikram",
            property_value_inr=20000000,
            consent_level=ConsentLevel.READ_ONLY,
        ))

        assert result.status == AgentStatus.SUCCESS
        assert result.verdict == "NOT_ADVISED"


# ══════════════════════════════════════════════════════════════
# BLOCK 7: PLANNER (THE WHOLE SYSTEM)
# ══════════════════════════════════════════════════════════════

class TestPlannerOrchestration:

    def test_full_review_runs_all_agents(self, sunita):
        graph = make_graph(sunita)
        planner = FinancialPlanner(graph)

        response = planner.run(PlannerRequest(
            user_id="sunita",
            intent=PlannerIntent.FULL_REVIEW,
            consent_level=ConsentLevel.READ_ONLY,
            params={"monthly_sip_inr": 50000},
        ))

        for expected in ["risk", "portfolio", "tax", "retirement"]:
            assert expected in response.agent_results


    def test_health_score_between_0_and_1(self, rohan):
        graph = make_graph(rohan)
        planner = FinancialPlanner(graph)

        response = planner.run(PlannerRequest(
            user_id="rohan",
            intent=PlannerIntent.FULL_REVIEW,
            consent_level=ConsentLevel.READ_ONLY,
        ))

        assert 0.0 <= response.overall_health_score <= 1.0
