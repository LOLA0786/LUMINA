"""
LUMINA API Routes
All endpoints. Clean, versioned, documented.

POST /api/v1/users                    — onboard user
GET  /api/v1/users/{user_id}          — get twin status
POST /api/v1/users/{user_id}/accounts — add bank account
POST /api/v1/users/{user_id}/holdings — add demat holding
POST /api/v1/users/{user_id}/loans    — add loan
POST /api/v1/users/{user_id}/income   — add income stream
POST /api/v1/users/{user_id}/events   — fire financial event
POST /api/v1/users/{user_id}/advice   — get AI advice
GET  /api/v1/advisor/{advisor_id}/brief — RM morning brief
GET  /api/v1/health                   — system health
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lumina.api.models import (
    AddBankAccountRequest, AddHoldingRequest,
    AddIncomeRequest, AddLoanRequest,
    AdviceRequest, AdviceResponse,
    AdvisorBriefResponse, EventResponse,
    FireEventRequest, HealthResponse,
    UserCreate, UserResponse,
)
from lumina.observability.logging import bind_context, get_logger
from lumina.observability.health import check_health

logger = get_logger("lumina.api")
router = APIRouter(prefix="/api/v1")


def _get_os():
    from lumina.api.app import financial_os
    return financial_os


def _get_repo():
    from lumina.api.app import twin_repo
    return twin_repo


# ── Users ─────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(req: UserCreate):
    bind_context(user_id=req.user_id)
    from lumina.packages.digital_twin.financial_twin import (
        FinancialTwin, IncomeStream,
    )
    os_ = _get_os()
    repo = _get_repo()

    if req.user_id in os_._sessions:
        raise HTTPException(400, f"User {req.user_id} already onboarded")

    twin = FinancialTwin(req.user_id, req.age, req.risk_score)
    twin.add_income_stream(
        IncomeStream("primary", "employer", req.monthly_income_inr, True)
    )
    repo.save_twin(twin)
    os_.onboard_user(twin)

    logger.info("api.user_created", user_id=req.user_id)
    return UserResponse(
        user_id               = twin.user_id,
        age                   = twin.current.age,
        risk_score            = twin.current.risk_score,
        net_worth_inr         = twin.current.net_worth_inr,
        total_assets_inr      = twin.current.total_assets_inr,
        total_liabilities_inr = twin.current.total_liabilities_inr,
        monthly_income_inr    = twin.current.monthly_income_inr,
        snapshots             = len(twin.history),
        message               = "User onboarded successfully",
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    bind_context(user_id=user_id)
    os_ = _get_os()
    repo = _get_repo()

    session = os_._sessions.get(user_id)
    if not session:
        twin = repo.load_twin(user_id)
        if not twin:
            raise HTTPException(404, f"User {user_id} not found")
        os_.onboard_user(twin)
        session = os_._sessions[user_id]

    twin = session.twin
    return UserResponse(
        user_id               = user_id,
        age                   = twin.current.age,
        risk_score            = twin.current.risk_score,
        net_worth_inr         = twin.current.net_worth_inr,
        total_assets_inr      = twin.current.total_assets_inr,
        total_liabilities_inr = twin.current.total_liabilities_inr,
        monthly_income_inr    = twin.current.monthly_income_inr,
        snapshots             = len(twin.history),
    )


# ── Assets ───────────────────────────────────────────────────────────

@router.post("/users/{user_id}/accounts", status_code=201)
def add_bank_account(user_id: str, req: AddBankAccountRequest):
    bind_context(user_id=user_id)
    from lumina.packages.digital_twin.financial_twin import (
        BankAccount, AccountType,
    )
    session = _require_session(user_id)
    try:
        account_type = AccountType(req.account_type)
    except ValueError:
        raise HTTPException(400, f"Invalid account_type: {req.account_type}")

    session.twin.add_bank_account(
        BankAccount(req.account_id, req.bank_name, account_type, req.balance_inr)
    )
    _get_repo().save_twin(session.twin)
    return {
        "message":        "Bank account added",
        "net_worth_inr":  session.twin.current.net_worth_inr,
        "snapshots":      len(session.twin.history),
    }


@router.post("/users/{user_id}/holdings", status_code=201)
def add_holding(user_id: str, req: AddHoldingRequest):
    bind_context(user_id=user_id)
    from lumina.packages.digital_twin.financial_twin import (
        DematHolding, HoldingType,
    )
    session = _require_session(user_id)
    try:
        holding_type = HoldingType(req.holding_type)
    except ValueError:
        raise HTTPException(400, f"Invalid holding_type: {req.holding_type}")

    session.twin.add_holding(
        DematHolding(
            req.holding_id, req.name, holding_type,
            req.units, req.nav_or_price_inr,
        )
    )
    _get_repo().save_twin(session.twin)
    return {
        "message":       "Holding added",
        "net_worth_inr": session.twin.current.net_worth_inr,
    }


@router.post("/users/{user_id}/loans", status_code=201)
def add_loan(user_id: str, req: AddLoanRequest):
    bind_context(user_id=user_id)
    from lumina.packages.digital_twin.financial_twin import Loan, LoanType
    session = _require_session(user_id)
    try:
        loan_type = LoanType(req.loan_type)
    except ValueError:
        raise HTTPException(400, f"Invalid loan_type: {req.loan_type}")

    session.twin.add_loan(Loan(
        req.loan_id, loan_type, req.lender,
        req.principal_inr, req.outstanding_inr,
        req.interest_rate_pct, req.emi_inr,
        req.tenure_months_remaining,
    ))
    _get_repo().save_twin(session.twin)
    return {
        "message":             "Loan added",
        "net_worth_inr":       session.twin.current.net_worth_inr,
        "total_liabilities":   session.twin.current.total_liabilities_inr,
    }


@router.post("/users/{user_id}/income", status_code=201)
def add_income(user_id: str, req: AddIncomeRequest):
    bind_context(user_id=user_id)
    from lumina.packages.digital_twin.financial_twin import IncomeStream
    session = _require_session(user_id)
    session.twin.add_income_stream(
        IncomeStream(req.stream_id, req.source, req.monthly_inr, req.is_primary)
    )
    _get_repo().save_twin(session.twin)
    return {
        "message":            "Income stream added",
        "monthly_income_inr": session.twin.current.monthly_income_inr,
    }


# ── Events ───────────────────────────────────────────────────────────

@router.post("/users/{user_id}/events", response_model=EventResponse)
def fire_event(user_id: str, req: FireEventRequest):
    bind_context(user_id=user_id)
    from lumina.packages.event_engine.financial_events import (
        EventType, FinancialEvent, EventSeverity,
    )
    _require_session(user_id)

    try:
        event_type = EventType(req.event_type)
    except ValueError:
        raise HTTPException(400, f"Unknown event_type: {req.event_type}")

    event = FinancialEvent(
        event_type = event_type,
        user_id    = user_id,
        severity   = EventSeverity.ADVISORY,
        payload    = req.payload,
        source     = req.source,
    )
    result = _get_os().process_event(event)

    if result.get("status") == "error":
        raise HTTPException(400, result.get("reason", "event processing failed"))

    return EventResponse(
        status           = result["status"],
        event            = result["event"],
        debate_verdict   = result["debate_verdict"],
        recommendation   = result["recommendation"],
        policy_result    = result["policy_result"],
        violations       = result.get("violations", []),
        flags            = result.get("flags", []),
        ledger_entry     = result["ledger_entry"],
        merkle_root      = result.get("merkle_root"),
        requires_approval= result.get("requires_approval", True),
    )


# ── Advice ───────────────────────────────────────────────────────────

@router.post("/users/{user_id}/advice", response_model=AdviceResponse)
def get_advice(user_id: str, req: AdviceRequest):
    bind_context(user_id=user_id)
    from lumina.packages.ai_agents.graph.wealth_graph import (
        WealthGraph, UserFinancialProfile, AssetNode,
    )
    from lumina.packages.ai_agents.planner.financial_planner import (
        FinancialPlanner, PlannerIntent, PlannerRequest,
    )
    from lumina.packages.ai_agents.core.base_agent import ConsentLevel

    session = _require_session(user_id)
    twin = session.twin.current

    # Bridge Digital Twin → WealthGraph for agent suite
    graph = WealthGraph()
    assets = [
        AssetNode(f"bank_{a.account_id}", "cash", a.balance_inr)
        for a in twin.bank_accounts
    ] + [
        AssetNode(h.holding_id, h.holding_type.value, h.current_value_inr)
        for h in twin.demat_holdings
    ] + [
        AssetNode(p.property_id, "real_estate", p.current_value_inr)
        for p in twin.property_assets
    ]
    from lumina.packages.ai_agents.graph.wealth_graph import LiabilityNode
    liabilities = [
        LiabilityNode(
            l.loan_id, l.loan_type.value,
            l.outstanding_inr, l.interest_rate_pct,
            l.tenure_months_remaining,
        )
        for l in twin.loans
    ]
    profile = UserFinancialProfile(
        user_id              = user_id,
        monthly_income_inr   = twin.monthly_income_inr or 100000,
        monthly_expenses_inr = twin.monthly_income_inr * 0.5,
        age                  = twin.age,
        risk_score           = twin.risk_score,
        assets               = assets,
        liabilities          = liabilities,
    )
    graph.load_fixture(profile)
    planner = FinancialPlanner(graph)

    try:
        intent = PlannerIntent(req.intent)
    except ValueError:
        intent = PlannerIntent.FULL_REVIEW

    response = planner.run(PlannerRequest(
        user_id       = user_id,
        intent        = intent,
        consent_level = ConsentLevel(req.consent_level),
        params        = req.params,
    ))

    return AdviceResponse(
        user_id           = user_id,
        intent            = req.intent,
        health_score      = response.overall_health_score,
        executive_summary = response.executive_summary,
        agent_results     = response.agent_results,
    )


# ── Advisor brief ─────────────────────────────────────────────────────

@router.get(
    "/advisor/{advisor_id}/brief",
    response_model=AdvisorBriefResponse,
)
def get_advisor_brief(advisor_id: str, client_ids: str = ""):
    bind_context(user_id=advisor_id)
    clients = [c.strip() for c in client_ids.split(",") if c.strip()]
    if not clients:
        clients = list(_get_os()._sessions.keys())

    brief = _get_os().generate_advisor_brief(advisor_id, clients)
    return AdvisorBriefResponse(
        advisor_id          = brief.advisor_id,
        generated_at        = brief.generated_at,
        p0_alert_count      = len(brief.p0_alerts),
        p1_alert_count      = len(brief.p1_alerts),
        total_aum_at_risk_inr = brief.total_aum_at_risk_inr,
        alerts              = [
            {
                "client_id":           a.client_id,
                "alert_type":          a.alert_type,
                "priority":            a.priority.value,
                "summary":             a.summary,
                "recommended_action":  a.recommended_action,
                "amount_at_stake_inr": a.amount_at_stake_inr,
            }
            for a in brief.alerts
        ],
        audit_summary       = brief.audit_summary,
        brief_text          = brief.render(),
    )


# ── Health ────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health():
    h = check_health(_get_os())
    return HealthResponse(**h.as_dict())


# ── Helpers ───────────────────────────────────────────────────────────

def _require_session(user_id: str):
    os_ = _get_os()
    repo = _get_repo()
    session = os_._sessions.get(user_id)
    if not session:
        twin = repo.load_twin(user_id)
        if twin:
            os_.onboard_user(twin)
            return os_._sessions[user_id]
        raise HTTPException(404, f"User {user_id} not found. POST /users first.")
    return session
