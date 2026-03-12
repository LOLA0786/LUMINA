"""
LUMINA Integration Test — Full Planner Run
Run with: pytest lumina/packages/ai_agents/tests/
"""

import pytest

from lumina.packages.ai_agents.agents.house_purchase.agent import HousePurchaseAgent, HousePurchaseInput
from lumina.packages.ai_agents.core.base_agent import ConsentLevel
from lumina.packages.ai_agents.graph.wealth_graph import AssetNode, LiabilityNode, UserFinancialProfile, WealthGraph
from lumina.packages.ai_agents.planner.financial_planner import FinancialPlanner, PlannerIntent, PlannerRequest


@pytest.fixture
def sample_profile():
    return UserFinancialProfile(
        user_id="test_user_001",
        monthly_income_inr=150000,
        monthly_expenses_inr=70000,
        age=32,
        risk_score=0.65,
        assets=[
            AssetNode("a1", "equity", 800000),
            AssetNode("a2", "cash", 200000),
            AssetNode("a3", "real_estate", 3000000),
        ],
        liabilities=[
            LiabilityNode("l1", "home_loan", 2000000, 8.5, 180),
        ],
    )


@pytest.fixture
def graph(sample_profile):
    g = WealthGraph()
    g.load_fixture(sample_profile)
    return g


def test_house_purchase_affordable(graph):
    agent = HousePurchaseAgent(graph)
    result = agent(HousePurchaseInput(
        user_id="test_user_001",
        property_value_inr=5000000,
        consent_level=ConsentLevel.READ_ONLY,
    ))
    assert result.status.value == "success"
    assert result.verdict in ("AFFORDABLE", "STRETCH", "NOT_ADVISED")
    assert result.monthly_emi_inr and result.monthly_emi_inr > 0


def test_full_financial_review(graph):
    planner = FinancialPlanner(graph)
    response = planner.run(PlannerRequest(
        user_id="test_user_001",
        intent=PlannerIntent.FULL_REVIEW,
        consent_level=ConsentLevel.READ_ONLY,
        params={"target_retirement_age": 55, "monthly_sip_inr": 20000},
    ))
    assert "risk" in response.agent_results
    assert "portfolio" in response.agent_results
    assert "retirement" in response.agent_results
    assert response.executive_summary != ""
    print("\n" + response.executive_summary)


def test_consent_blocked(graph):
    agent = HousePurchaseAgent(graph)
    result = agent(HousePurchaseInput(
        user_id="test_user_001",
        property_value_inr=5000000,
        consent_level=ConsentLevel.NONE,
    ))
    assert result.status.value == "blocked"
