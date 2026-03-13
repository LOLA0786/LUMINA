"""
LUMINA Financial OS — End-to-End Integration Tests
Full stack: Twin → Events → Debate → Policy → Ledger
"""
import pytest

from lumina.packages.digital_twin.financial_twin import (
    AccountType, BankAccount, DematHolding, FinancialTwin,
    HoldingType, IncomeStream, Loan, LoanType,
)
from lumina.packages.event_engine.financial_events import (
    market_crash, salary_credited, goal_at_risk, loan_closed,
)
from lumina.packages.event_engine.financial_events import EventSeverity
from lumina.packages.governance.audit_ledger import AuditLedger
from lumina.packages.governance.policy_engine import (
    PolicyDecision, PolicyEngine, PolicyResult,
)
from lumina.packages.execution_layer.execution_request import (
    ActionType, ExecutionRequest,
)
from lumina.packages.financial_os.financial_os import FinancialOS


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def rohan_twin():
    twin = FinancialTwin(user_id="rohan_os", age=34, risk_score=0.75)
    twin.add_bank_account(
        BankAccount("b1", "HDFC", AccountType.SAVINGS, 350000)
    )
    twin.add_holding(
        DematHolding("h1", "Nifty 50 Index Fund", HoldingType.EQUITY_MF, 100, 2800)
    )
    twin.add_income_stream(
        IncomeStream("i1", "employer", 220000, is_primary=True)
    )
    return twin


@pytest.fixture
def rich_twin():
    """Well-funded user — all policy checks should pass."""
    twin = FinancialTwin(user_id="rich_os", age=40, risk_score=0.60)
    twin.add_bank_account(
        BankAccount("b1", "ICICI", AccountType.SAVINGS, 5000000)
    )
    twin.add_holding(
        DematHolding("h1", "Large Cap Fund", HoldingType.EQUITY_MF, 500, 3000)
    )
    twin.add_income_stream(
        IncomeStream("i1", "employer", 500000, is_primary=True)
    )
    return twin


@pytest.fixture
def os_instance():
    return FinancialOS()


# ── Block 1: Financial Digital Twin ──────────────────────────────────

class TestFinancialTwin:

    def test_chain_valid_after_mutations(self, rohan_twin):
        rohan_twin.update_bank_balance("b1", 400000)
        rohan_twin.update_bank_balance("b1", 500000)
        assert rohan_twin.state_chain_valid()

    def test_net_worth_increases_on_deposit(self, rohan_twin):
        before = rohan_twin.current.net_worth_inr
        rohan_twin.update_bank_balance("b1", 700000)
        assert rohan_twin.current.net_worth_inr > before

    def test_history_is_append_only(self, rohan_twin):
        before = len(rohan_twin.history)
        rohan_twin.update_bank_balance("b1", 500000)
        assert len(rohan_twin.history) == before + 1

    def test_liquid_assets_equity_haircut(self, rohan_twin):
        # Bank ₹3.5L × 1.0  = ₹3,50,000
        # MF   100u × ₹2800 × 0.80 = ₹2,24,000
        expected = 350000 + (100 * 2800 * 0.80)
        assert abs(rohan_twin.current.total_liquid_inr - expected) < 1

    def test_loan_reduces_net_worth(self, rohan_twin):
        before = rohan_twin.current.net_worth_inr
        rohan_twin.add_loan(
            Loan("l1", LoanType.PERSONAL, "HDFC", 200000, 200000, 14.0, 10000, 24)
        )
        assert rohan_twin.current.net_worth_inr < before

    def test_tampered_chain_detected(self, rohan_twin):
        rohan_twin.update_bank_balance("b1", 999999)
        # Tamper silently
        rohan_twin._history[0].state_hash = "tampered00000000"
        assert not rohan_twin.state_chain_valid()


# ── Block 2: Event Engine ─────────────────────────────────────────────

class TestEventEngine:

    def test_salary_event_fields(self):
        e = salary_credited("rohan_os", 220000, "TechCorp")
        assert e.user_id == "rohan_os"
        assert e.payload["amount_inr"] == 220000
        assert not e.processed

    def test_market_crash_critical_above_15pct(self):
        e = market_crash("rohan_os", 20.0, ["NIFTY50"])
        assert e.severity == EventSeverity.CRITICAL

    def test_market_crash_alert_below_15pct(self):
        e = market_crash("rohan_os", 10.0, ["NIFTY50"])
        assert e.severity == EventSeverity.ALERT

    def test_event_bus_handler_fires(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        fired = []
        from lumina.packages.event_engine.financial_events import EventType
        os_instance.event_bus.subscribe(
            EventType.SALARY_CREDITED, lambda e: fired.append(e)
        )
        e = salary_credited("rohan_os", 220000, "TechCorp")
        os_instance.event_bus.publish(e)
        assert len(fired) == 1
        assert fired[0].processed

    def test_event_marked_processed_after_publish(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        e = salary_credited("rohan_os", 220000, "TechCorp")
        os_instance.event_bus.publish(e)
        assert e.processed


# ── Block 3: Governance ───────────────────────────────────────────────

class TestGovernance:

    def test_liquidity_breach_blocked(self):
        engine = PolicyEngine()
        req = ExecutionRequest(
            user_id     = "test",
            action_type = ActionType.REBALANCE,
            amount_inr  = 400000,
            confidence  = 0.85,
        )
        profile = {
            "consent_level":       "read_only",
            "risk_score":          0.5,
            "liquid_assets_inr":   350000,
            "total_assets_inr":    5000000,
            "monthly_expenses_inr": 70000,   # emergency fund = ₹4.2L
        }
        d = engine.evaluate(req, profile)
        assert d.result == PolicyResult.BLOCKED

    def test_safe_action_allowed(self):
        engine = PolicyEngine()
        req = ExecutionRequest(
            user_id     = "test",
            action_type = ActionType.SIP_ADJUST,
            amount_inr  = 20000,
            confidence  = 0.88,
        )
        profile = {
            "consent_level":       "read_only",
            "risk_score":          0.7,
            "liquid_assets_inr":   2000000,
            "total_assets_inr":    10000000,
            "monthly_expenses_inr": 70000,
        }
        d = engine.evaluate(req, profile)
        assert d.result == PolicyResult.ALLOWED

    def test_no_consent_blocked(self):
        engine = PolicyEngine()
        req = ExecutionRequest(
            user_id     = "test",
            action_type = ActionType.SIP_ADJUST,
            amount_inr  = 5000,
            confidence  = 0.90,
        )
        profile = {
            "consent_level":       "none",
            "risk_score":          0.5,
            "liquid_assets_inr":   5000000,
            "total_assets_inr":    10000000,
            "monthly_expenses_inr": 50000,
        }
        d = engine.evaluate(req, profile)
        assert d.result == PolicyResult.BLOCKED

    def test_low_confidence_flagged(self):
        engine = PolicyEngine()
        req = ExecutionRequest(
            user_id     = "test",
            action_type = ActionType.SIP_ADJUST,
            amount_inr  = 5000,
            confidence  = 0.40,    # below 0.60 threshold
        )
        profile = {
            "consent_level":       "read_only",
            "risk_score":          0.5,
            "liquid_assets_inr":   5000000,
            "total_assets_inr":    10000000,
            "monthly_expenses_inr": 50000,
        }
        d = engine.evaluate(req, profile)
        assert d.result == PolicyResult.FLAGGED

    def test_merkle_chain_valid_after_5_entries(self):
        ledger = AuditLedger()
        for i in range(5):
            d = PolicyDecision(
                request_id   = f"req_{i}",
                result       = PolicyResult.ALLOWED,
                receipt_hash = f"hash_{i}",
            )
            ledger.record(d, "user_001", "sip_adjust")
        assert ledger.verify_integrity()
        assert ledger.merkle_root is not None

    def test_tampered_ledger_detected(self):
        ledger = AuditLedger()
        d = PolicyDecision(
            request_id   = "req_0",
            result       = PolicyResult.ALLOWED,
            receipt_hash = "hash_0",
        )
        ledger.record(d, "user_001", "sip_adjust")
        ledger._entries[0].policy_result = "blocked"   # tamper
        assert not ledger.verify_integrity()

    def test_merkle_root_changes_on_new_entry(self):
        ledger = AuditLedger()
        d1 = PolicyDecision(request_id="r1", result=PolicyResult.ALLOWED, receipt_hash="h1")
        ledger.record(d1, "u1", "sip_adjust")
        root1 = ledger.merkle_root
        d2 = PolicyDecision(request_id="r2", result=PolicyResult.BLOCKED, receipt_hash="h2")
        ledger.record(d2, "u1", "rebalance")
        assert ledger.merkle_root != root1


# ── Block 4: Financial OS (full pipeline) ────────────────────────────

class TestFinancialOS:

    def test_onboard_user(self, rohan_twin, os_instance):
        session = os_instance.onboard_user(rohan_twin)
        assert session.user_id == "rohan_os"
        assert session.twin.current.net_worth_inr > 0

    def test_unknown_user_returns_error(self, os_instance):
        e = salary_credited("ghost", 100000, "Nobody")
        result = os_instance.process_event(e)
        assert result["status"] == "error"
        assert result["reason"] == "user_not_onboarded"

    def test_salary_event_processed(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        e = salary_credited("rohan_os", 220000, "TechCorp")
        result = os_instance.process_event(e)
        assert result["status"] == "processed"
        assert result["policy_result"] in ("allowed", "blocked", "flagged")
        assert result["merkle_root"] is not None

    def test_market_crash_processed(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        e = market_crash("rohan_os", 20.0, ["NIFTY50", "SENSEX"])
        result = os_instance.process_event(e)
        assert result["status"] == "processed"

    def test_audit_chain_grows_with_events(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        for _ in range(4):
            os_instance.process_event(
                salary_credited("rohan_os", 220000, "TechCorp")
            )
        summary = os_instance.audit_summary
        assert summary["total_entries"] == 4
        assert summary["chain_valid"]

    def test_advisor_brief_generated(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        brief = os_instance.generate_advisor_brief("advisor_001", ["rohan_os"])
        assert brief.advisor_id == "advisor_001"
        rendered = brief.render()
        assert "LUMINA ADVISOR BRIEF" in rendered

    def test_advisor_brief_flags_liquidity_risk(self, rohan_twin, os_instance):
        # Rohan has low liquid vs income — should trigger P0 alert
        os_instance.onboard_user(rohan_twin)
        brief = os_instance.generate_advisor_brief("advisor_001", ["rohan_os"])
        liquidity_alerts = [
            a for a in brief.alerts if a.alert_type == "LIQUIDITY_RISK"
        ]
        assert len(liquidity_alerts) > 0

    def test_rich_user_no_liquidity_alert(self, rich_twin, os_instance):
        os_instance.onboard_user(rich_twin)
        brief = os_instance.generate_advisor_brief("advisor_001", ["rich_os"])
        liquidity_alerts = [
            a for a in brief.alerts if a.alert_type == "LIQUIDITY_RISK"
        ]
        assert len(liquidity_alerts) == 0

    def test_session_stats_tracked(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        os_instance.process_event(salary_credited("rohan_os", 220000, "TechCorp"))
        os_instance.process_event(market_crash("rohan_os", 10.0, ["NIFTY"]))
        session = os_instance._sessions["rohan_os"]
        assert session.events_processed == 2

    def test_merkle_root_in_advisor_brief(self, rohan_twin, os_instance):
        os_instance.onboard_user(rohan_twin)
        os_instance.process_event(salary_credited("rohan_os", 220000, "TechCorp"))
        brief = os_instance.generate_advisor_brief("advisor_001", ["rohan_os"])
        assert brief.audit_summary.get("merkle_root") is not None
        assert brief.audit_summary.get("chain_valid") is True
