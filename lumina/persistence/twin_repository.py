"""
LUMINA Twin Repository
Save and load FinancialTwin snapshots to/from DB.

The Twin is the source of truth.
The DB is just persistence — the Twin's logic never changes.

TwinRepository.save(twin)  → persists all new snapshots
TwinRepository.load(user_id) → reconstructs Twin from DB
"""
from __future__ import annotations

import json
import time
from typing import Optional

from lumina.digital_twin.financial_twin import (
    AccountType, BankAccount, DematHolding, FinancialGoal,
    FinancialTwin, GoalType, HoldingType, IncomeStream,
    InsurancePolicy, Loan, LoanType, PropertyAsset, TaxProfile,
)
from lumina.observability.logging import get_logger
from lumina.persistence.database import get_connection

logger = get_logger("lumina.persistence.twin")


def _snapshot_to_payload(snap) -> dict:
    """Serialize a TwinSnapshot to a JSON-safe dict."""
    def _ser(obj):
        if hasattr(obj, "__dict__"):
            return {k: _ser(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [_ser(i) for i in obj]
        if hasattr(obj, "value"):
            return obj.value
        return obj

    return {
        "bank_accounts":      [_ser(a) for a in snap.bank_accounts],
        "demat_holdings":     [_ser(h) for h in snap.demat_holdings],
        "property_assets":    [_ser(p) for p in snap.property_assets],
        "loans":              [_ser(l) for l in snap.loans],
        "insurance_policies": [_ser(i) for i in snap.insurance_policies],
        "income_streams":     [_ser(s) for s in snap.income_streams],
        "tax_profile":        _ser(snap.tax_profile),
        "financial_goals":    [_ser(g) for g in snap.financial_goals],
        "age":                snap.age,
        "risk_score":         snap.risk_score,
    }


class TwinRepository:
    """
    Persists FinancialTwin snapshots to SQLite/Postgres.
    The interface never changes — only DATABASE_URL changes.
    """

    def upsert_user(
        self, user_id: str, age: int, risk_score: float
    ) -> None:
        now = time.time()
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO users (user_id, age, risk_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    age        = excluded.age,
                    risk_score = excluded.risk_score,
                    updated_at = excluded.updated_at
            """, (user_id, age, risk_score, now, now))
        logger.info("user.upserted", user_id=user_id)

    def save_snapshot(self, snap) -> None:
        payload = json.dumps(_snapshot_to_payload(snap))
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
        """Persist all snapshots not yet in DB."""
        self.upsert_user(
            twin.user_id,
            twin.current.age,
            twin.current.risk_score,
        )
        saved = self._saved_snapshot_ids(twin.user_id)
        new_snaps = [
            s for s in twin.history
            if s.snapshot_id not in saved
        ]
        for snap in new_snaps:
            self.save_snapshot(snap)
        logger.info(
            "twin.saved",
            user_id       = twin.user_id,
            new_snapshots = len(new_snaps),
        )

    def load_twin(self, user_id: str) -> Optional[FinancialTwin]:
        """Reconstruct a FinancialTwin from DB snapshots."""
        rows = self._load_snapshot_rows(user_id)
        if not rows:
            logger.info("twin.not_found", user_id=user_id)
            return None

        # Get age + risk from latest snapshot payload
        latest_payload = json.loads(rows[-1]["payload"])
        twin = FinancialTwin(
            user_id    = user_id,
            age        = latest_payload["age"],
            risk_score = latest_payload["risk_score"],
        )

        # Re-apply mutations in order to rebuild history
        for row in rows[1:]:   # skip genesis (already created)
            payload = json.loads(row["payload"])
            twin._mutate(
                bank_accounts      = _deserialize_accounts(payload),
                demat_holdings     = _deserialize_holdings(payload),
                property_assets    = _deserialize_properties(payload),
                loans              = _deserialize_loans(payload),
                insurance_policies = _deserialize_insurance(payload),
                income_streams     = _deserialize_income(payload),
                tax_profile        = _deserialize_tax(payload),
                financial_goals    = _deserialize_goals(payload),
                age                = payload["age"],
                risk_score         = payload["risk_score"],
            )

        logger.info(
            "twin.loaded",
            user_id   = user_id,
            snapshots = len(twin.history),
            net_worth = twin.current.net_worth_inr,
        )
        return twin

    def _saved_snapshot_ids(self, user_id: str) -> set[str]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT snapshot_id FROM twin_snapshots WHERE user_id = ?",
                (user_id,)
            ).fetchall()
        return {r["snapshot_id"] for r in rows}

    def _load_snapshot_rows(self, user_id: str) -> list:
        with get_connection() as conn:
            return conn.execute("""
                SELECT * FROM twin_snapshots
                WHERE user_id = ?
                ORDER BY timestamp ASC
            """, (user_id,)).fetchall()


# ── Deserializers ────────────────────────────────────────────────────

def _deserialize_accounts(p: dict) -> list[BankAccount]:
    return [
        BankAccount(
            a["account_id"], a["bank_name"],
            AccountType(a["account_type"]),
            a["balance_inr"],
            a.get("last_updated", time.time()),
        )
        for a in p.get("bank_accounts", [])
    ]

def _deserialize_holdings(p: dict) -> list[DematHolding]:
    return [
        DematHolding(
            h["holding_id"], h["name"],
            HoldingType(h["holding_type"]),
            h["units"], h["nav_or_price_inr"],
            h.get("folio_id", ""),
        )
        for h in p.get("demat_holdings", [])
    ]

def _deserialize_properties(p: dict) -> list[PropertyAsset]:
    return [
        PropertyAsset(
            pr["property_id"], pr["description"], pr["city"],
            pr["purchase_value_inr"], pr["current_value_inr"],
            pr.get("is_self_occupied", True),
            pr.get("monthly_rental_inr", 0.0),
        )
        for pr in p.get("property_assets", [])
    ]

def _deserialize_loans(p: dict) -> list[Loan]:
    return [
        Loan(
            l["loan_id"], LoanType(l["loan_type"]),
            l["lender"], l["principal_inr"],
            l["outstanding_inr"], l["interest_rate_pct"],
            l["emi_inr"], l["tenure_months_remaining"],
        )
        for l in p.get("loans", [])
    ]

def _deserialize_insurance(p: dict) -> list[InsurancePolicy]:
    return [
        InsurancePolicy(
            i["policy_id"], i["insurer"], i["policy_type"],
            i["sum_assured_inr"], i["annual_premium_inr"],
            i.get("maturity_year"),
        )
        for i in p.get("insurance_policies", [])
    ]

def _deserialize_income(p: dict) -> list[IncomeStream]:
    return [
        IncomeStream(
            s["stream_id"], s["source"], s["monthly_inr"],
            s.get("is_primary", False), s.get("is_taxable", True),
        )
        for s in p.get("income_streams", [])
    ]

def _deserialize_tax(p: dict) -> TaxProfile:
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

def _deserialize_goals(p: dict) -> list[FinancialGoal]:
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
