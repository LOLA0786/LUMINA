"""
LUMINA Twin Repository
Save and load FinancialTwin snapshots to/from DB.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from lumina.packages.digital_twin.financial_twin import (
    AccountType, BankAccount, DematHolding, FinancialGoal,
    FinancialTwin, GoalType, HoldingType, IncomeStream,
    InsurancePolicy, Loan, LoanType, PropertyAsset, TaxProfile,
)
from lumina.observability.logging import get_logger
from lumina.persistence.database import get_connection

logger = get_logger("lumina.persistence.twin")


def _snap_to_dict(snap) -> dict:
    """Safely serialize a TwinSnapshot — no recursion."""

    def account(a) -> dict:
        return {
            "account_id":   a.account_id,
            "bank_name":    a.bank_name,
            "account_type": a.account_type.value,
            "balance_inr":  a.balance_inr,
            "last_updated": a.last_updated,
        }

    def holding(h) -> dict:
        return {
            "holding_id":       h.holding_id,
            "name":             h.name,
            "holding_type":     h.holding_type.value,
            "units":            h.units,
            "nav_or_price_inr": h.nav_or_price_inr,
            "folio_id":         h.folio_id,
        }

    def prop(p) -> dict:
        return {
            "property_id":        p.property_id,
            "description":        p.description,
            "city":               p.city,
            "purchase_value_inr": p.purchase_value_inr,
            "current_value_inr":  p.current_value_inr,
            "is_self_occupied":   p.is_self_occupied,
            "monthly_rental_inr": p.monthly_rental_inr,
        }

    def loan(l) -> dict:
        return {
            "loan_id":                  l.loan_id,
            "loan_type":                l.loan_type.value,
            "lender":                   l.lender,
            "principal_inr":            l.principal_inr,
            "outstanding_inr":          l.outstanding_inr,
            "interest_rate_pct":        l.interest_rate_pct,
            "emi_inr":                  l.emi_inr,
            "tenure_months_remaining":  l.tenure_months_remaining,
        }

    def insurance(i) -> dict:
        return {
            "policy_id":         i.policy_id,
            "insurer":           i.insurer,
            "policy_type":       i.policy_type,
            "sum_assured_inr":   i.sum_assured_inr,
            "annual_premium_inr":i.annual_premium_inr,
            "maturity_year":     i.maturity_year,
        }

    def income(s) -> dict:
        return {
            "stream_id":   s.stream_id,
            "source":      s.source,
            "monthly_inr": s.monthly_inr,
            "is_primary":  s.is_primary,
            "is_taxable":  s.is_taxable,
        }

    def tax(t) -> dict:
        return {
            "pan":                    t.pan,
            "preferred_regime":       t.preferred_regime,
            "deductions_80c_inr":     t.deductions_80c_inr,
            "deductions_80d_inr":     t.deductions_80d_inr,
            "hra_exemption_inr":      t.hra_exemption_inr,
            "nps_80ccd_inr":          t.nps_80ccd_inr,
            "home_loan_interest_inr": t.home_loan_interest_inr,
        }

    def goal(g) -> dict:
        return {
            "goal_id":              g.goal_id,
            "goal_type":            g.goal_type.value,
            "description":          g.description,
            "target_amount_inr":    g.target_amount_inr,
            "target_year":          g.target_year,
            "current_savings_inr":  g.current_savings_inr,
            "monthly_sip_inr":      g.monthly_sip_inr,
        }

    return {
        "bank_accounts":      [account(a) for a in snap.bank_accounts],
        "demat_holdings":     [holding(h) for h in snap.demat_holdings],
        "property_assets":    [prop(p)    for p in snap.property_assets],
        "loans":              [loan(l)    for l in snap.loans],
        "insurance_policies": [insurance(i) for i in snap.insurance_policies],
        "income_streams":     [income(s)  for s in snap.income_streams],
        "tax_profile":        tax(snap.tax_profile),
        "financial_goals":    [goal(g)    for g in snap.financial_goals],
        "age":                snap.age,
        "risk_score":         snap.risk_score,
    }


class TwinRepository:

    def upsert_user(self, user_id: str, age: int, risk_score: float) -> None:
        now = time.time()
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO users (user_id, age, risk_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    age=excluded.age,
                    risk_score=excluded.risk_score,
                    updated_at=excluded.updated_at
            """, (user_id, age, risk_score, now, now))
        logger.info("user.upserted", user_id=user_id)

    def save_snapshot(self, snap) -> None:
        payload = json.dumps(_snap_to_dict(snap))
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO twin_snapshots
                (snapshot_id, user_id, timestamp, state_hash,
                 net_worth_inr, total_assets, total_liabs, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snap.snapshot_id,
                snap.user_id,
                snap.timestamp,
                snap.state_hash,
                snap.net_worth_inr,
                snap.total_assets_inr,
                snap.total_liabilities_inr,
                payload,
            ))
        logger.info(
            "snapshot.saved",
            snapshot_id = snap.snapshot_id[:8],
            net_worth   = snap.net_worth_inr,
        )

    def save_twin(self, twin: FinancialTwin) -> None:
        self.upsert_user(
            twin.user_id,
            twin.current.age,
            twin.current.risk_score,
        )
        saved = self._saved_ids(twin.user_id)
        new_snaps = [s for s in twin.history if s.snapshot_id not in saved]
        for snap in new_snaps:
            self.save_snapshot(snap)
        logger.info(
            "twin.saved",
            user_id       = twin.user_id,
            new_snapshots = len(new_snaps),
        )

    def load_twin(self, user_id: str) -> Optional[FinancialTwin]:
        rows = self._load_rows(user_id)
        if not rows:
            return None
        latest = json.loads(rows[-1]["payload"])
        twin = FinancialTwin(
            user_id    = user_id,
            age        = latest["age"],
            risk_score = latest["risk_score"],
        )
        for row in rows[1:]:
            p = json.loads(row["payload"])
            twin._mutate(
                bank_accounts      = _deser_accounts(p),
                demat_holdings     = _deser_holdings(p),
                property_assets    = _deser_props(p),
                loans              = _deser_loans(p),
                insurance_policies = _deser_insurance(p),
                income_streams     = _deser_income(p),
                tax_profile        = _deser_tax(p),
                financial_goals    = _deser_goals(p),
                age                = p["age"],
                risk_score         = p["risk_score"],
            )
        logger.info(
            "twin.loaded",
            user_id   = user_id,
            snapshots = len(twin.history),
        )
        return twin

    def _saved_ids(self, user_id: str) -> set[str]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT snapshot_id FROM twin_snapshots WHERE user_id=?",
                (user_id,)
            ).fetchall()
        return {r["snapshot_id"] for r in rows}

    def _load_rows(self, user_id: str) -> list:
        with get_connection() as conn:
            return conn.execute("""
                SELECT * FROM twin_snapshots
                WHERE user_id=? ORDER BY timestamp ASC
            """, (user_id,)).fetchall()


# ── Deserializers ────────────────────────────────────────────────────

def _deser_accounts(p: dict) -> list:
    return [
        BankAccount(
            a["account_id"], a["bank_name"],
            AccountType(a["account_type"]),
            a["balance_inr"], a.get("last_updated", time.time()),
        )
        for a in p.get("bank_accounts", [])
    ]

def _deser_holdings(p: dict) -> list:
    return [
        DematHolding(
            h["holding_id"], h["name"],
            HoldingType(h["holding_type"]),
            h["units"], h["nav_or_price_inr"],
            h.get("folio_id", ""),
        )
        for h in p.get("demat_holdings", [])
    ]

def _deser_props(p: dict) -> list:
    return [
        PropertyAsset(
            pr["property_id"], pr["description"], pr["city"],
            pr["purchase_value_inr"], pr["current_value_inr"],
            pr.get("is_self_occupied", True),
            pr.get("monthly_rental_inr", 0.0),
        )
        for pr in p.get("property_assets", [])
    ]

def _deser_loans(p: dict) -> list:
    return [
        Loan(
            l["loan_id"], LoanType(l["loan_type"]),
            l["lender"], l["principal_inr"],
            l["outstanding_inr"], l["interest_rate_pct"],
            l["emi_inr"], l["tenure_months_remaining"],
        )
        for l in p.get("loans", [])
    ]

def _deser_insurance(p: dict) -> list:
    return [
        InsurancePolicy(
            i["policy_id"], i["insurer"], i["policy_type"],
            i["sum_assured_inr"], i["annual_premium_inr"],
            i.get("maturity_year"),
        )
        for i in p.get("insurance_policies", [])
    ]

def _deser_income(p: dict) -> list:
    return [
        IncomeStream(
            s["stream_id"], s["source"], s["monthly_inr"],
            s.get("is_primary", False), s.get("is_taxable", True),
        )
        for s in p.get("income_streams", [])
    ]

def _deser_tax(p: dict) -> TaxProfile:
    t = p.get("tax_profile", {})
    return TaxProfile(
        pan                    = t.get("pan", ""),
        preferred_regime       = t.get("preferred_regime", "NEW"),
        deductions_80c_inr     = t.get("deductions_80c_inr", 0),
        deductions_80d_inr     = t.get("deductions_80d_inr", 0),
        hra_exemption_inr      = t.get("hra_exemption_inr", 0),
        nps_80ccd_inr          = t.get("nps_80ccd_inr", 0),
        home_loan_interest_inr = t.get("home_loan_interest_inr", 0),
    )

def _deser_goals(p: dict) -> list:
    return [
        FinancialGoal(
            g["goal_id"], GoalType(g["goal_type"]),
            g["description"], g["target_amount_inr"],
            g["target_year"],
            g.get("current_savings_inr", 0),
            g.get("monthly_sip_inr", 0),
        )
        for g in p.get("financial_goals", [])
    ]
