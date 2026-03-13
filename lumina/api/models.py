"""
LUMINA API Request/Response Models
Pydantic models for all API endpoints.
These are the contract between LUMINA and the outside world.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── User ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    user_id: str
    age: int = Field(ge=18, le=100)
    risk_score: float = Field(ge=0.0, le=1.0)
    monthly_income_inr: float = Field(gt=0)
    monthly_expenses_inr: float = Field(gt=0)

class UserResponse(BaseModel):
    user_id: str
    age: int
    risk_score: float
    net_worth_inr: float
    total_assets_inr: float
    total_liabilities_inr: float
    monthly_income_inr: float
    snapshots: int
    message: str = "ok"


# ── Assets ───────────────────────────────────────────────────────────

class AddBankAccountRequest(BaseModel):
    account_id: str
    bank_name: str
    account_type: str = "savings"
    balance_inr: float = Field(ge=0)

class AddHoldingRequest(BaseModel):
    holding_id: str
    name: str
    holding_type: str = "equity_mf"
    units: float = Field(gt=0)
    nav_or_price_inr: float = Field(gt=0)

class AddLoanRequest(BaseModel):
    loan_id: str
    loan_type: str = "home_loan"
    lender: str
    principal_inr: float = Field(gt=0)
    outstanding_inr: float = Field(gt=0)
    interest_rate_pct: float = Field(gt=0)
    emi_inr: float = Field(gt=0)
    tenure_months_remaining: int = Field(gt=0)

class AddIncomeRequest(BaseModel):
    stream_id: str
    source: str
    monthly_inr: float = Field(gt=0)
    is_primary: bool = False


# ── Events ───────────────────────────────────────────────────────────

class FireEventRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = "api"

class EventResponse(BaseModel):
    status: str
    event: str
    debate_verdict: str
    recommendation: str
    policy_result: str
    violations: list[str]
    flags: list[str]
    ledger_entry: str
    merkle_root: Optional[str]
    requires_approval: bool


# ── Advice ───────────────────────────────────────────────────────────

class AdviceRequest(BaseModel):
    intent: str = "full_review"
    params: dict[str, Any] = Field(default_factory=dict)
    consent_level: str = "read_only"

class AdviceResponse(BaseModel):
    user_id: str
    intent: str
    health_score: Optional[float]
    executive_summary: str
    agent_results: dict[str, Any]
    message: str = "ok"


# ── Advisor ──────────────────────────────────────────────────────────

class AdvisorBriefResponse(BaseModel):
    advisor_id: str
    generated_at: float
    p0_alert_count: int
    p1_alert_count: int
    total_aum_at_risk_inr: float
    alerts: list[dict]
    audit_summary: dict
    brief_text: str


# ── Health ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_s: float
    components: list[dict]
    checked_at: str
