"""
LUMINA Wealth Graph Client
──────────────────────────
Thin abstraction over the financial knowledge graph.
Agents query this — never raw DB connections.

Nodes  : User, Asset, Liability, Account, Goal, LifeEvent
Edges  : owns, funds, hedges, impacts, triggers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AssetNode:
    asset_id: str
    asset_type: str          # equity | real_estate | crypto | cash | pension
    current_value_inr: float
    currency: str = "INR"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LiabilityNode:
    liability_id: str
    liability_type: str      # home_loan | personal_loan | credit_card
    outstanding_inr: float
    interest_rate_pct: float
    tenure_months_remaining: int


@dataclass
class UserFinancialProfile:
    user_id: str
    monthly_income_inr: float
    monthly_expenses_inr: float
    age: int
    risk_score: float          # 0.0 (very conservative) → 1.0 (aggressive)
    assets: list[AssetNode] = field(default_factory=list)
    liabilities: list[LiabilityNode] = field(default_factory=list)
    goals: list[dict[str, Any]] = field(default_factory=list)

    @property
    def net_worth_inr(self) -> float:
        return (
            sum(a.current_value_inr for a in self.assets)
            - sum(l.outstanding_inr for l in self.liabilities)
        )

    @property
    def monthly_surplus_inr(self) -> float:
        return self.monthly_income_inr - self.monthly_expenses_inr

    @property
    def debt_to_income_ratio(self) -> float:
        total_debt = sum(l.outstanding_inr for l in self.liabilities)
        annual_income = self.monthly_income_inr * 12
        return total_debt / annual_income if annual_income else 0.0


class WealthGraph:
    """
    In production: wraps a Neo4j / Neptune / Tigergraph client.
    In tests / dev: loads from JSON fixture.
    """

    def __init__(self, driver: Any = None):
        self._driver = driver
        self._cache: dict[str, UserFinancialProfile] = {}

    def get_profile(self, user_id: str) -> Optional[UserFinancialProfile]:
        if user_id in self._cache:
            return self._cache[user_id]
        # TODO: replace with real graph query
        return None

    def upsert_profile(self, profile: UserFinancialProfile) -> None:
        self._cache[profile.user_id] = profile

    def load_fixture(self, profile: UserFinancialProfile) -> None:
        """For tests and demos — inject a profile directly."""
        self._cache[profile.user_id] = profile
