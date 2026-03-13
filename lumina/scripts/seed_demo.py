"""
LUMINA Demo Seed Script
═══════════════════════
Creates 3 real Indian client profiles, fires events,
runs the full agent suite, prints the advisor brief.

One command. Full system demo. Investor-ready.

Run: python -m lumina.scripts.seed_demo
"""
from __future__ import annotations

import json
import time

from lumina.config.settings import settings
from lumina.observability.logging import configure_logging, get_logger
from lumina.packages.ai_agents.core.base_agent import ConsentLevel
from lumina.packages.ai_agents.graph.wealth_graph import (
    AssetNode, LiabilityNode, UserFinancialProfile, WealthGraph,
)
from lumina.packages.ai_agents.planner.financial_planner import (
    FinancialPlanner, PlannerIntent, PlannerRequest,
)
from lumina.packages.digital_twin.financial_twin import (
    AccountType, BankAccount, DematHolding, FinancialGoal,
    FinancialTwin, GoalType, HoldingType, IncomeStream,
    InsurancePolicy, Loan, LoanType, PropertyAsset, TaxProfile,
)
from lumina.packages.event_engine.financial_events import (
    goal_at_risk, loan_closed, market_crash, salary_credited,
)
from lumina.packages.financial_os.financial_os import FinancialOS
from lumina.persistence.database import init_db
from lumina.persistence.twin_repository import TwinRepository

configure_logging(level="WARNING", json_output=False)
logger = get_logger("lumina.seed")

SEP  = "═" * 64
SEP2 = "─" * 64


def header(text: str) -> None:
    print(f"\n{SEP}")
    print(f"  {text}")
    print(SEP)


def section(text: str) -> None:
    print(f"\n{SEP2}")
    print(f"  {text}")
    print(SEP2)


# ════════════════════════════════════════════════════════════════════
# CLIENT PROFILES
# ════════════════════════════════════════════════════════════════════

def build_rohan() -> FinancialTwin:
    """
    Rohan Mehta, 34, Bangalore.
    Senior SDE at a startup. ₹2.2L/mo.
    Heavy equity, wants to buy a flat.
    Classic DINK tech professional.
    """
    twin = FinancialTwin("rohan_mehta", age=34, risk_score=0.75)
    twin.add_bank_account(
        BankAccount("r_b1", "HDFC", AccountType.SAVINGS, 350000)
    )
    twin.add_holding(
        DematHolding("r_h1", "Nifty 50 Index Fund",
                     HoldingType.EQUITY_MF, 180, 2800)
    )
    twin.add_holding(
        DematHolding("r_h2", "Mirae Asset Large Cap",
                     HoldingType.EQUITY_MF, 90, 1200)
    )
    twin.add_holding(
        DematHolding("r_h3", "Parag Parikh Flexi Cap",
                     HoldingType.EQUITY_MF, 60, 800)
    )
    twin.add_income_stream(
        IncomeStream("r_i1", "employer", 220000, is_primary=True)
    )
    twin.add_goal(FinancialGoal(
        "r_g1", GoalType.HOUSE,
        "Buy 2BHK in Bangalore",
        target_amount_inr  = 10000000,
        target_year        = 2027,
        current_savings_inr= 3500000,
        monthly_sip_inr    = 30000,
    ))
    twin.set_tax_profile(TaxProfile(
        pan                = "ABCPR1234D",
        preferred_regime   = "NEW",
        deductions_80c_inr = 80000,
        deductions_80d_inr = 10000,
    ))
    return twin


def build_sunita() -> FinancialTwin:
    """
    Sunita Krishnan, 52, Mumbai.
    Partner at a CA firm. ₹5.5L/mo.
    Owns 2 properties. Retiring at 58.
    High income, under-invested in equity.
    """
    twin = FinancialTwin("sunita_krishnan", age=52, risk_score=0.35)
    twin.add_bank_account(
        BankAccount("s_b1", "ICICI", AccountType.SAVINGS, 800000)
    )
    twin.add_bank_account(
        BankAccount("s_b2", "SBI", AccountType.FD, 2500000)
    )
    twin.add_holding(
        DematHolding("s_h1", "HDFC Large Cap Fund",
                     HoldingType.EQUITY_MF, 200, 3000)
    )
    twin.add_holding(
        DematHolding("s_h2", "ICICI Pru Balanced Adv",
                     HoldingType.DEBT_MF, 500, 800)
    )

    twin._mutate(property_assets=[
        PropertyAsset(
            "s_p1", "3BHK Bandra West", "Mumbai",
            15000000, 22000000, is_self_occupied=True,
        ),
        PropertyAsset(
            "s_p2", "2BHK Powai", "Mumbai",
            6000000, 9000000, is_self_occupied=False,
            monthly_rental_inr=45000,
        ),
    ])
    twin.add_loan(Loan(
        "s_l1", LoanType.HOME, "HDFC Bank",
        6000000, 4000000, 8.75, 52000, 72,
    ))
    twin.add_income_stream(
        IncomeStream("s_i1", "employer", 550000, is_primary=True)
    )
    twin.add_income_stream(
        IncomeStream("s_i2", "rental", 45000, is_primary=False)
    )
    twin.add_goal(FinancialGoal(
        "s_g1", GoalType.RETIREMENT,
        "Retire at 58 with ₹2L/mo spend",
        target_amount_inr   = 30000000,
        target_year         = 2032,
        current_savings_inr = 8500000,
        monthly_sip_inr     = 100000,
    ))
    twin.set_tax_profile(TaxProfile(
        pan                    = "BCDPS5678E",
        preferred_regime       = "OLD",
        deductions_80c_inr     = 150000,
        deductions_80d_inr     = 25000,
        nps_80ccd_inr          = 50000,
        hra_exemption_inr      = 200000,
        home_loan_interest_inr = 200000,
    ))
    return twin


def build_vikram() -> FinancialTwin:
    """
    Vikram Nair, 28, Pune.
    IT services, first job. ₹65K/mo.
    Barely saving. High-risk loan. Zero insurance.
    Classic early-career client.
    """
    twin = FinancialTwin("vikram_nair", age=28, risk_score=0.80)
    twin.add_bank_account(
        BankAccount("v_b1", "Kotak", AccountType.SAVINGS, 45000)
    )
    twin.add_loan(Loan(
        "v_l1", LoanType.PERSONAL, "Bajaj Finance",
        150000, 120000, 14.0, 7500, 18,
    ))
    twin.add_income_stream(
        IncomeStream("v_i1", "employer", 65000, is_primary=True)
    )
    twin.add_goal(FinancialGoal(
        "v_g1", GoalType.EMERGENCY,
        "Build 6-month emergency fund",
        target_amount_inr   = 330000,
        target_year         = 2026,
        current_savings_inr = 45000,
        monthly_sip_inr     = 5000,
    ))
    twin.set_tax_profile(TaxProfile(
        pan                = "CDQVN9012F",
        preferred_regime   = "NEW",
        deductions_80c_inr = 0,
    ))
    return twin


# ════════════════════════════════════════════════════════════════════
# DEMO RUNNER
# ════════════════════════════════════════════════════════════════════

def run_demo() -> None:
    header("LUMINA FINANCIAL OS — LIVE DEMO")
    print(f"  Version     : {settings.app_version}")
    print(f"  Environment : {settings.environment}")
    print(f"  DB          : {settings.database_url}")

    # ── Init ──────────────────────────────────────────────────────
    init_db()
    repo = TwinRepository()
    os_  = FinancialOS()

    # ── Build + persist clients ───────────────────────────────────
    section("STEP 1 — Building Financial Digital Twins")
    clients = {
        "rohan_mehta":    build_rohan(),
        "sunita_krishnan": build_sunita(),
        "vikram_nair":    build_vikram(),
    }
    for name, twin in clients.items():
        repo.save_twin(twin)
        os_.onboard_user(twin)
        print(
            f"  ✓ {name:22} "
            f"net_worth=₹{twin.current.net_worth_inr/1e7:.2f}Cr  "
            f"snapshots={len(twin.history)}"
        )

    # ── Fire events ───────────────────────────────────────────────
    section("STEP 2 — Firing Financial Events")

    events = [
        ("rohan_mehta",     salary_credited("rohan_mehta", 220000, "TechCorp")),
        ("sunita_krishnan", salary_credited("sunita_krishnan", 550000, "CA Firm")),
        ("vikram_nair",     salary_credited("vikram_nair", 65000, "Infosys")),
        ("rohan_mehta",     market_crash("rohan_mehta", 12.0, ["NIFTY50"])),
        ("vikram_nair",     goal_at_risk("vikram_nair", "v_g1", 285000)),
        ("sunita_krishnan", loan_closed("sunita_krishnan", "s_l1", 52000)),
    ]

    for user_id, event in events:
        result = os_.process_event(event)
        icon = (
            "✓" if result["policy_result"] == "allowed"  else
            "⚠" if result["policy_result"] == "flagged"  else
            "✗"
        )
        print(
            f"  {icon} [{user_id[:14]:14}] "
            f"{event.event_type.value:25} "
            f"→ {result['policy_result']:8} "
            f"merkle={result['merkle_root'][:10]}..."
        )

    # ── Run full AI advice suite ──────────────────────────────────
    section("STEP 3 — AI Advice Engine (Full Review)")

    client_profiles = {
        "rohan_mehta": UserFinancialProfile(
            user_id              = "rohan_mehta",
            monthly_income_inr   = 220000,
            monthly_expenses_inr = 90000,
            age=34, risk_score=0.75,
            assets=[
                AssetNode("r1", "equity", 756000),
                AssetNode("r2", "cash", 350000),
            ],
        ),
        "sunita_krishnan": UserFinancialProfile(
            user_id              = "sunita_krishnan",
            monthly_income_inr   = 595000,
            monthly_expenses_inr = 180000,
            age=52, risk_score=0.35,
            assets=[
                AssetNode("s1", "real_estate", 31000000),
                AssetNode("s2", "equity", 760000),
                AssetNode("s3", "cash", 3300000),
            ],
            liabilities=[
                LiabilityNode("sl1","home_loan",4000000,8.75,72),
            ],
        ),
        "vikram_nair": UserFinancialProfile(
            user_id              = "vikram_nair",
            monthly_income_inr   = 65000,
            monthly_expenses_inr = 55000,
            age=28, risk_score=0.80,
            assets=[AssetNode("v1","cash",45000)],
            liabilities=[
                LiabilityNode("vl1","personal_loan",120000,14.0,18),
            ],
        ),
    }

    for user_id, profile in client_profiles.items():
        graph = WealthGraph()
        graph.load_fixture(profile)
        planner = FinancialPlanner(graph)
        response = planner.run(PlannerRequest(
            user_id       = user_id,
            intent        = PlannerIntent.FULL_REVIEW,
            consent_level = ConsentLevel.READ_ONLY,
            params        = {"monthly_sip_inr": 20000},
        ))
        score = response.overall_health_score or 0
        grade = (
            "EXCELLENT" if score > 0.80 else
            "GOOD"      if score > 0.60 else
            "NEEDS WORK"
        )
        print(f"\n  [{user_id}]")
        print(f"    Health  : {grade} ({score:.0%})")
        print(f"    Summary : {response.executive_summary}")

    # ── Merkle audit summary ──────────────────────────────────────
    section("STEP 4 — Governance Audit (PrivateVault Merkle Log)")
    summary = os_.audit_summary
    print(f"  Total decisions  : {summary['total_entries']}")
    print(f"  Merkle root      : {str(summary['merkle_root'])[:32]}...")
    print(f"  Chain integrity  : {'✓ VALID' if summary['chain_valid'] else '✗ BROKEN'}")
    bd = summary.get("breakdown", {})
    print(f"  Allowed          : {bd.get('allowed', 0)}")
    print(f"  Flagged          : {bd.get('flagged', 0)}")
    print(f"  Blocked          : {bd.get('blocked', 0)}")

    # ── Advisor brief ─────────────────────────────────────────────
    section("STEP 5 — Advisor Morning Brief")
    brief = os_.generate_advisor_brief(
        "advisor_001",
        list(clients.keys()),
    )
    print(brief.render())

    # ── Final scoreboard ─────────────────────────────────────────
    header("DEMO COMPLETE")
    print(f"  Clients onboarded  : {len(clients)}")
    print(f"  Events processed   : {sum(s.events_processed for s in os_._sessions.values())}")
    print(f"  Audit entries      : {summary['total_entries']}")
    print(f"  Chain valid        : {'✓ YES' if summary['chain_valid'] else '✗ NO'}")
    print(f"  Snapshots persisted: {sum(len(t.history) for t in clients.values())}")
    print()
    print("  Start API:  uvicorn lumina.api.app:app --reload --port 8000")
    print("  API docs:   http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    run_demo()
