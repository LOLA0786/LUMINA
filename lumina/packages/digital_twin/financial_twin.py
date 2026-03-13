"""
LUMINA Financial Digital Twin
Git for money. Permanent financial state machine.
Every change = new immutable snapshot, hash-linked.
"""
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AccountType(str, Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    FD = "fd"
    RD = "rd"

class HoldingType(str, Enum):
    EQUITY_MF = "equity_mf"
    DEBT_MF   = "debt_mf"
    ETF       = "etf"
    STOCK     = "stock"
    BOND      = "bond"
    GOLD      = "gold"

class LoanType(str, Enum):
    HOME      = "home_loan"
    PERSONAL  = "personal_loan"
    VEHICLE   = "vehicle_loan"
    EDUCATION = "education_loan"
    CREDIT    = "credit_card"

class GoalType(str, Enum):
    RETIREMENT = "retirement"
    HOUSE      = "house_purchase"
    EDUCATION  = "child_education"
    EMERGENCY  = "emergency_fund"
    WEALTH     = "wealth_creation"


@dataclass
class BankAccount:
    account_id: str
    bank_name: str
    account_type: AccountType
    balance_inr: float
    last_updated: float = field(default_factory=time.time)

@dataclass
class DematHolding:
    holding_id: str
    name: str
    holding_type: HoldingType
    units: float
    nav_or_price_inr: float
    folio_id: str = ""

    @property
    def current_value_inr(self) -> float:
        return self.units * self.nav_or_price_inr

@dataclass
class PropertyAsset:
    property_id: str
    description: str
    city: str
    purchase_value_inr: float
    current_value_inr: float
    is_self_occupied: bool = True
    monthly_rental_inr: float = 0.0

@dataclass
class Loan:
    loan_id: str
    loan_type: LoanType
    lender: str
    principal_inr: float
    outstanding_inr: float
    interest_rate_pct: float
    emi_inr: float
    tenure_months_remaining: int

@dataclass
class InsurancePolicy:
    policy_id: str
    insurer: str
    policy_type: str
    sum_assured_inr: float
    annual_premium_inr: float
    maturity_year: Optional[int] = None

@dataclass
class IncomeStream:
    stream_id: str
    source: str
    monthly_inr: float
    is_primary: bool = False
    is_taxable: bool = True

@dataclass
class TaxProfile:
    pan: str
    preferred_regime: str = "NEW"
    deductions_80c_inr: float = 0
    deductions_80d_inr: float = 0
    hra_exemption_inr: float = 0
    nps_80ccd_inr: float = 0
    home_loan_interest_inr: float = 0

@dataclass
class FinancialGoal:
    goal_id: str
    goal_type: GoalType
    description: str
    target_amount_inr: float
    target_year: int
    current_savings_inr: float = 0
    monthly_sip_inr: float = 0

    @property
    def years_remaining(self) -> int:
        return max(0, self.target_year - int(time.strftime("%Y")))

    @property
    def progress_pct(self) -> float:
        if self.target_amount_inr == 0:
            return 0
        return min(100, self.current_savings_inr / self.target_amount_inr * 100)


@dataclass
class TwinSnapshot:
    snapshot_id: str
    user_id: str
    timestamp: float
    state_hash: str
    bank_accounts: list
    demat_holdings: list
    property_assets: list
    loans: list
    insurance_policies: list
    income_streams: list
    tax_profile: TaxProfile
    financial_goals: list
    age: int
    risk_score: float

    @property
    def total_liquid_inr(self) -> float:
        bank = sum(a.balance_inr for a in self.bank_accounts)
        demat = sum(
            h.current_value_inr * (
                0.80 if h.holding_type in (HoldingType.EQUITY_MF, HoldingType.STOCK, HoldingType.ETF)
                else 1.0
            )
            for h in self.demat_holdings
        )
        return bank + demat

    @property
    def total_assets_inr(self) -> float:
        return (
            sum(a.balance_inr for a in self.bank_accounts)
            + sum(h.current_value_inr for h in self.demat_holdings)
            + sum(p.current_value_inr for p in self.property_assets)
        )

    @property
    def total_liabilities_inr(self) -> float:
        return sum(l.outstanding_inr for l in self.loans)

    @property
    def net_worth_inr(self) -> float:
        return self.total_assets_inr - self.total_liabilities_inr

    @property
    def monthly_income_inr(self) -> float:
        return sum(s.monthly_inr for s in self.income_streams)

    @property
    def monthly_emi_outflow_inr(self) -> float:
        return sum(l.emi_inr for l in self.loans)


class FinancialTwin:
    """
    The Financial Digital Twin.
    Append-only snapshot history. Every mutation = new snapshot.
    Chain is cryptographically verified like a blockchain.
    """

    def __init__(self, user_id: str, age: int, risk_score: float):
        self.user_id = user_id
        self._history: list[TwinSnapshot] = []
        self._current = TwinSnapshot(
            snapshot_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=time.time(),
            state_hash="",
            bank_accounts=[],
            demat_holdings=[],
            property_assets=[],
            loans=[],
            insurance_policies=[],
            income_streams=[],
            tax_profile=TaxProfile(pan=""),
            financial_goals=[],
            age=age,
            risk_score=risk_score,
        )
        self._seal(self._current)

    def _seal(self, snap: TwinSnapshot) -> None:
        data = {
            "net_worth": snap.net_worth_inr,
            "total_assets": snap.total_assets_inr,
            "total_liabilities": snap.total_liabilities_inr,
            "timestamp": snap.timestamp,
            "prev": self._history[-1].state_hash if self._history else "genesis",
        }
        snap.state_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]
        self._history.append(snap)

    def _mutate(self, **kwargs) -> TwinSnapshot:
        import copy
        base = {
            "snapshot_id": str(uuid.uuid4()),
            "user_id": self.user_id,
            "timestamp": time.time(),
            "state_hash": "",
            "bank_accounts":      copy.deepcopy(self._current.bank_accounts),
            "demat_holdings":     copy.deepcopy(self._current.demat_holdings),
            "property_assets":    copy.deepcopy(self._current.property_assets),
            "loans":              copy.deepcopy(self._current.loans),
            "insurance_policies": copy.deepcopy(self._current.insurance_policies),
            "income_streams":     copy.deepcopy(self._current.income_streams),
            "tax_profile":        copy.deepcopy(self._current.tax_profile),
            "financial_goals":    copy.deepcopy(self._current.financial_goals),
            "age":                self._current.age,
            "risk_score":         self._current.risk_score,
        }
        base.update(kwargs)
        snap = TwinSnapshot(**base)
        self._seal(snap)
        self._current = snap
        return snap

    def add_bank_account(self, a: BankAccount) -> TwinSnapshot:
        return self._mutate(bank_accounts=self._current.bank_accounts + [a])

    def update_bank_balance(self, account_id: str, new_balance: float) -> TwinSnapshot:
        updated = [
            BankAccount(a.account_id, a.bank_name, a.account_type,
                        new_balance, time.time())
            if a.account_id == account_id else a
            for a in self._current.bank_accounts
        ]
        return self._mutate(bank_accounts=updated)

    def add_holding(self, h: DematHolding) -> TwinSnapshot:
        return self._mutate(demat_holdings=self._current.demat_holdings + [h])

    def add_loan(self, l: Loan) -> TwinSnapshot:
        return self._mutate(loans=self._current.loans + [l])

    def add_goal(self, g: FinancialGoal) -> TwinSnapshot:
        return self._mutate(financial_goals=self._current.financial_goals + [g])

    def add_income_stream(self, s: IncomeStream) -> TwinSnapshot:
        return self._mutate(income_streams=self._current.income_streams + [s])

    def set_tax_profile(self, p: TaxProfile) -> TwinSnapshot:
        return self._mutate(tax_profile=p)

    @property
    def current(self) -> TwinSnapshot:
        return self._current

    @property
    def history(self) -> list[TwinSnapshot]:
        return list(self._history)

    def state_chain_valid(self) -> bool:
        for i, snap in enumerate(self._history):
            prev = self._history[i-1].state_hash if i > 0 else "genesis"
            data = {
                "net_worth": snap.net_worth_inr,
                "total_assets": snap.total_assets_inr,
                "total_liabilities": snap.total_liabilities_inr,
                "timestamp": snap.timestamp,
                "prev": prev,
            }
            expected = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()[:16]
            if snap.state_hash != expected:
                return False
        return True
