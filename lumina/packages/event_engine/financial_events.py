"""
LUMINA Financial Event Engine
Event-driven finance. The system reacts to the world.
12 event types covering everything that changes a financial life.
"""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    SALARY_CREDITED      = "salary_credited"
    BONUS_RECEIVED       = "bonus_received"
    DIVIDEND_RECEIVED    = "dividend_received"
    RENTAL_INCOME        = "rental_income"
    MARKET_CRASH         = "market_crash"
    RATE_CHANGE          = "rate_change"
    NAV_UPDATE           = "nav_update"
    INFLATION_UPDATE     = "inflation_update"
    LOAN_DISBURSED       = "loan_disbursed"
    EMI_DEBITED          = "emi_debited"
    LOAN_CLOSED          = "loan_closed"
    RATE_HIKE_ON_LOAN    = "rate_hike_on_loan"
    TAX_LAW_CHANGE       = "tax_law_change"
    RBI_POLICY_CHANGE    = "rbi_policy_change"
    SEBI_RULE_CHANGE     = "sebi_rule_change"
    MARRIAGE             = "marriage"
    CHILD_BORN           = "child_born"
    JOB_CHANGE           = "job_change"
    INHERITANCE_RECEIVED = "inheritance_received"
    HEALTH_EMERGENCY     = "health_emergency"
    GOAL_REACHED         = "goal_reached"
    GOAL_AT_RISK         = "goal_at_risk"
    SIP_MISSED           = "sip_missed"


class EventSeverity(str, Enum):
    INFO     = "info"
    ADVISORY = "advisory"
    ALERT    = "alert"
    CRITICAL = "critical"


@dataclass
class FinancialEvent:
    event_id: str            = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType    = EventType.SALARY_CREDITED
    user_id: str             = ""
    timestamp: float         = field(default_factory=time.time)
    severity: EventSeverity  = EventSeverity.INFO
    payload: dict[str, Any]  = field(default_factory=dict)
    source: str              = "system"
    processed: bool          = False


# ── Convenience constructors ─────────────────────────────────────────

def salary_credited(user_id: str, amount_inr: float, employer: str) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.SALARY_CREDITED,
        user_id=user_id,
        severity=EventSeverity.ADVISORY,
        payload={"amount_inr": amount_inr, "employer": employer},
        source="bank",
    )

def bonus_received(user_id: str, amount_inr: float) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.BONUS_RECEIVED,
        user_id=user_id,
        severity=EventSeverity.ADVISORY,
        payload={"amount_inr": amount_inr},
        source="bank",
    )

def market_crash(user_id: str, drawdown_pct: float, affected_indices: list) -> FinancialEvent:
    severity = EventSeverity.CRITICAL if drawdown_pct > 15 else EventSeverity.ALERT
    return FinancialEvent(
        event_type=EventType.MARKET_CRASH,
        user_id=user_id,
        severity=severity,
        payload={"drawdown_pct": drawdown_pct, "affected_indices": affected_indices},
        source="market_feed",
    )

def rate_change(user_id: str, old_rate: float, new_rate: float, effective_from: str) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.RATE_CHANGE,
        user_id=user_id,
        severity=EventSeverity.ALERT,
        payload={"old_rate": old_rate, "new_rate": new_rate, "effective_from": effective_from},
        source="rbi_feed",
    )

def tax_law_change(user_id: str, description: str, impact_summary: str) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.TAX_LAW_CHANGE,
        user_id=user_id,
        severity=EventSeverity.ALERT,
        payload={"description": description, "impact_summary": impact_summary},
        source="regulatory",
    )

def goal_at_risk(user_id: str, goal_id: str, shortfall_inr: float) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.GOAL_AT_RISK,
        user_id=user_id,
        severity=EventSeverity.ALERT,
        payload={"goal_id": goal_id, "shortfall_inr": shortfall_inr},
        source="system",
    )

def health_emergency(user_id: str, estimated_cost_inr: float) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.HEALTH_EMERGENCY,
        user_id=user_id,
        severity=EventSeverity.CRITICAL,
        payload={"estimated_cost_inr": estimated_cost_inr},
        source="user",
    )

def loan_closed(user_id: str, loan_id: str, freed_emi_inr: float) -> FinancialEvent:
    return FinancialEvent(
        event_type=EventType.LOAN_CLOSED,
        user_id=user_id,
        severity=EventSeverity.ADVISORY,
        payload={"loan_id": loan_id, "freed_emi_inr": freed_emi_inr},
        source="bank",
    )
