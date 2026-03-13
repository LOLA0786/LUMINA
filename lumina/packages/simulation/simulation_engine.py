"""
LUMINA Simulation Engine
═════════════════════════
Real financial systems simulate future states.
What-if scenarios for advisors and clients.

Scenarios supported:
  MARKET_CRASH        — portfolio drops X%
  JOB_LOSS            — income drops to zero for N months
  RATE_HIKE           — loan EMI increases
  INFLATION_SPIKE     — expenses rise sharply
  EARLY_RETIREMENT    — retire N years earlier
  SALARY_GROWTH       — income grows at X% p.a.
  LARGE_EXPENSE       — one-time cost (wedding, medical)
  PROPERTY_PURCHASE   — buy property at price P

Output per scenario:
  net_worth_impact_inr
  liquidity_impact_inr
  retirement_probability_pct
  portfolio_drawdown_pct
  months_to_recovery
  risk_level: LOW / MEDIUM / HIGH / CRITICAL
  recommendations: list of actions

Monte Carlo used for retirement probability.
Everything else: deterministic projection.

This is what wealth advisors actually need.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.config.settings import settings
from lumina.observability.logging import get_logger

logger = get_logger("lumina.simulation")


class ScenarioType(str, Enum):
    MARKET_CRASH      = "market_crash"
    JOB_LOSS          = "job_loss"
    RATE_HIKE         = "rate_hike"
    INFLATION_SPIKE   = "inflation_spike"
    EARLY_RETIREMENT  = "early_retirement"
    SALARY_GROWTH     = "salary_growth"
    LARGE_EXPENSE     = "large_expense"
    PROPERTY_PURCHASE = "property_purchase"


class RiskLevel(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


def _risk_level(score: float) -> RiskLevel:
    if score >= 0.75:
        return RiskLevel.LOW
    if score >= 0.50:
        return RiskLevel.MEDIUM
    if score >= 0.25:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


@dataclass
class ScenarioParams:
    scenario_type: ScenarioType

    # MARKET_CRASH
    drawdown_pct: float = 0.30

    # JOB_LOSS
    income_loss_months: int = 6

    # RATE_HIKE
    rate_hike_bps: int = 200          # basis points

    # INFLATION_SPIKE
    inflation_pct: float = 0.10

    # EARLY_RETIREMENT
    retire_years_earlier: int = 5

    # SALARY_GROWTH
    annual_growth_pct: float = 0.10

    # LARGE_EXPENSE
    expense_inr: float = 500000

    # PROPERTY_PURCHASE
    property_price_inr: float = 10000000
    down_payment_pct: float   = 0.20

    # Monte Carlo
    monte_carlo_runs: int = 1000


@dataclass
class SimulationResult:
    scenario_type:            ScenarioType
    scenario_label:           str
    user_id:                  str
    net_worth_before_inr:     float
    net_worth_after_inr:      float
    net_worth_impact_inr:     float
    net_worth_impact_pct:     float
    liquidity_before_inr:     float
    liquidity_after_inr:      float
    liquidity_impact_inr:     float
    portfolio_drawdown_pct:   float
    retirement_probability_pct: float
    months_to_recovery:       Optional[int]
    risk_level:               RiskLevel
    findings:                 list[str]
    recommendations:          list[str]
    computed_at:              float = field(default_factory=time.time)
    monte_carlo_runs:         int   = 0
    metadata:                 dict  = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario":                   self.scenario_type.value,
            "label":                      self.scenario_label,
            "user_id":                    self.user_id,
            "risk_level":                 self.risk_level.value,
            "net_worth_before_inr":       self.net_worth_before_inr,
            "net_worth_after_inr":        self.net_worth_after_inr,
            "net_worth_impact_inr":       self.net_worth_impact_inr,
            "net_worth_impact_pct":       round(
                self.net_worth_impact_pct, 3
            ),
            "liquidity_before_inr":       self.liquidity_before_inr,
            "liquidity_after_inr":        self.liquidity_after_inr,
            "liquidity_impact_inr":       self.liquidity_impact_inr,
            "portfolio_drawdown_pct":     round(
                self.portfolio_drawdown_pct, 3
            ),
            "retirement_probability_pct": round(
                self.retirement_probability_pct, 1
            ),
            "months_to_recovery":         self.months_to_recovery,
            "findings":                   self.findings,
            "recommendations":            self.recommendations,
            "monte_carlo_runs":           self.monte_carlo_runs,
            "computed_at":                self.computed_at,
        }

    def render(self) -> str:
        impact_sign = "+" if self.net_worth_impact_inr >= 0 else ""
        lines = [
            "┌" + "─" * 56 + "┐",
            f"│  SIMULATION: {self.scenario_label:41}│",
            f"│  User: {self.user_id:48}│",
            f"│  Risk: {self.risk_level.value:48}│",
            "├" + "─" * 56 + "┤",
            f"│  Net worth before : ₹{self.net_worth_before_inr/1e7:>8.2f} Cr"
            f"{'':24}│",
            f"│  Net worth after  : ₹{self.net_worth_after_inr/1e7:>8.2f} Cr"
            f"{'':24}│",
            f"│  Impact           : "
            f"{impact_sign}₹{self.net_worth_impact_inr/1e5:>6.1f}L"
            f"  ({impact_sign}{self.net_worth_impact_pct:.1%})"
            f"{'':14}│",
            f"│  Liquidity after  : ₹{self.liquidity_after_inr/1e5:>6.1f}L"
            f"{'':29}│",
            f"│  Portfolio drop   : {self.portfolio_drawdown_pct:.1%}"
            f"{'':36}│",
            f"│  Retirement prob  : {self.retirement_probability_pct:.1f}%"
            f"{'':34}│",
        ]
        if self.months_to_recovery:
            lines.append(
                f"│  Recovery time    : "
                f"{self.months_to_recovery} months"
                f"{'':31}│"
            )
        lines.append("├" + "─" * 56 + "┤")
        lines.append(f"│  FINDINGS{'':46}│")
        for f_ in self.findings:
            lines.append(f"│  • {f_[:52]:52}│")
        lines.append("├" + "─" * 56 + "┤")
        lines.append(f"│  RECOMMENDATIONS{'':39}│")
        for r in self.recommendations:
            lines.append(f"│  → {r[:52]:52}│")
        lines.append("└" + "─" * 56 + "┘")
        return "\n".join(lines)


class SimulationEngine:
    """
    Runs what-if scenarios on a FinancialTwin.
    Does NOT mutate the twin — runs on a copy.

    Monte Carlo used for retirement probability:
      - 1000 runs with randomised returns (mean=10%, std=12%)
      - probability = runs where corpus >= target / total runs
    """

    def run(
        self,
        twin,
        params: ScenarioParams,
    ) -> SimulationResult:
        snap = twin.current
        start = time.perf_counter()

        logger.info(
            "simulation.start",
            user_id  = snap.user_id,
            scenario = params.scenario_type.value,
        )

        routes = {
            ScenarioType.MARKET_CRASH:      self._sim_market_crash,
            ScenarioType.JOB_LOSS:          self._sim_job_loss,
            ScenarioType.RATE_HIKE:         self._sim_rate_hike,
            ScenarioType.INFLATION_SPIKE:   self._sim_inflation_spike,
            ScenarioType.EARLY_RETIREMENT:  self._sim_early_retirement,
            ScenarioType.SALARY_GROWTH:     self._sim_salary_growth,
            ScenarioType.LARGE_EXPENSE:     self._sim_large_expense,
            ScenarioType.PROPERTY_PURCHASE: self._sim_property_purchase,
        }

        result = routes[params.scenario_type](snap, params)

        latency = (time.perf_counter() - start) * 1000
        logger.info(
            "simulation.complete",
            user_id    = snap.user_id,
            scenario   = params.scenario_type.value,
            risk_level = result.risk_level.value,
            latency_ms = round(latency, 2),
        )
        return result

    def run_all(
        self,
        twin,
        scenarios: Optional[list[ScenarioParams]] = None,
    ) -> list[SimulationResult]:
        """Run multiple scenarios. Returns all results."""
        if scenarios is None:
            scenarios = _default_scenarios()
        return [self.run(twin, s) for s in scenarios]

    # ── Scenario implementations ──────────────────────────────────

    def _sim_market_crash(self, snap, p: ScenarioParams) -> SimulationResult:
        equity_val = sum(
            h.current_value_inr for h in snap.demat_holdings
            if h.holding_type.value in ("equity_mf","etf","stock")
        )
        loss          = equity_val * p.drawdown_pct
        nw_after      = snap.net_worth_inr - loss
        liquid_after  = snap.total_liquid_inr - (
            loss * 0.80  # equity haircut
        )
        monthly_exp   = snap.monthly_income_inr * 0.50
        emergency     = monthly_exp * settings.emergency_fund_months

        # Recovery: SIP continues, market recovers at 10% p.a.
        if equity_val > 0 and snap.monthly_income_inr > 0:
            monthly_sip = sum(
                g.monthly_sip_inr for g in snap.financial_goals
            ) or (snap.monthly_income_inr * 0.10)
            months = _months_to_recover(loss, monthly_sip, 0.10)
        else:
            months = None

        ret_prob = self._monte_carlo_retirement(snap, p, shock=-p.drawdown_pct)
        findings = [
            f"Equity portfolio drops by ₹{loss/1e5:.1f}L ({p.drawdown_pct:.0%})",
            f"Net worth: ₹{snap.net_worth_inr/1e7:.2f}Cr → ₹{nw_after/1e7:.2f}Cr",
            f"Liquidity: ₹{snap.total_liquid_inr/1e5:.1f}L → ₹{max(0,liquid_after)/1e5:.1f}L",
            f"Emergency fund {'intact' if liquid_after >= emergency else 'BREACHED'}",
        ]
        recs = []
        if liquid_after < emergency:
            recs.append("Do NOT redeem equity — let it recover")
            recs.append("Pause new investments, preserve cash")
        else:
            recs.append("Step-up SIP by 25% — buy the dip")
            recs.append("Do not panic-sell equity positions")
        recs.append(f"Review in {months or 12} months")

        score = max(0, liquid_after) / max(1, snap.total_liquid_inr)
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Market crash -{p.drawdown_pct:.0%}",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = nw_after,
            net_worth_impact_inr      = -loss,
            net_worth_impact_pct      = -loss / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = max(0, liquid_after),
            liquidity_impact_inr      = -loss * 0.80,
            portfolio_drawdown_pct    = p.drawdown_pct,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = months,
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_job_loss(self, snap, p: ScenarioParams) -> SimulationResult:
        monthly_income = snap.monthly_income_inr
        monthly_exp    = monthly_income * 0.50
        monthly_emi    = snap.monthly_emi_outflow_inr
        monthly_burn   = monthly_exp + monthly_emi
        total_loss     = monthly_income * p.income_loss_months
        cash_burn      = monthly_burn * p.income_loss_months
        liquid_after   = snap.total_liquid_inr - cash_burn
        nw_after       = snap.net_worth_inr - total_loss

        months_runway  = int(
            snap.total_liquid_inr / monthly_burn
        ) if monthly_burn > 0 else 99

        ret_prob = self._monte_carlo_retirement(
            snap, p,
            income_gap_months=p.income_loss_months,
        )

        findings = [
            f"Income gap: ₹{total_loss/1e5:.1f}L over "
            f"{p.income_loss_months} months",
            f"Monthly burn: ₹{monthly_burn/1e3:.1f}K "
            f"(expenses + EMI)",
            f"Cash runway: {months_runway} months at current burn",
            f"Liquid after crisis: ₹{max(0,liquid_after)/1e5:.1f}L",
        ]
        recs = []
        if months_runway < p.income_loss_months:
            recs.append("CRITICAL: Liquid assets insufficient for gap")
            recs.append("Pause all SIPs immediately")
            recs.append("Consider loan moratorium if available")
        else:
            recs.append("Emergency fund covers the gap — stay calm")
            recs.append("Pause discretionary investments during gap")
        recs.append("Build 9-month fund after re-employment")

        score = max(0, months_runway) / max(1, p.income_loss_months + 3)
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Job loss {p.income_loss_months}mo",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = nw_after,
            net_worth_impact_inr      = -total_loss,
            net_worth_impact_pct      = -total_loss / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = max(0, liquid_after),
            liquidity_impact_inr      = -cash_burn,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = p.income_loss_months + 6,
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_rate_hike(self, snap, p: ScenarioParams) -> SimulationResult:
        rate_delta     = p.rate_hike_bps / 10000
        extra_emi      = sum(
            _emi_increase(l.outstanding_inr, rate_delta,
                          l.tenure_months_remaining)
            for l in snap.loans
        )
        annual_extra   = extra_emi * 12
        nw_after       = snap.net_worth_inr - annual_extra
        liquid_after   = snap.total_liquid_inr - extra_emi * 6

        findings = [
            f"Rate hike: +{p.rate_hike_bps}bps on all loans",
            f"Additional EMI: ₹{extra_emi:,.0f}/month",
            f"Annual impact: ₹{annual_extra/1e5:.1f}L",
            f"FOIR increases by "
            f"{extra_emi/max(1,snap.monthly_income_inr):.1%}",
        ]
        recs = []
        new_foir = (
            snap.monthly_emi_outflow_inr + extra_emi
        ) / max(1, snap.monthly_income_inr)
        if new_foir > settings.max_foir_pct:
            recs.append("FOIR breaches 50% — prepay highest rate loan")
            recs.append("Switch to fixed rate if variable loan")
        else:
            recs.append("FOIR still manageable — no immediate action")
            recs.append("Consider partial prepayment to reduce tenure")

        score = max(0, 1.0 - new_foir)
        ret_prob = self._monte_carlo_retirement(snap, p)
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Rate hike +{p.rate_hike_bps}bps",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = nw_after,
            net_worth_impact_inr      = -annual_extra,
            net_worth_impact_pct      = -annual_extra / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = max(0, liquid_after),
            liquidity_impact_inr      = -extra_emi * 6,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = None,
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_inflation_spike(self, snap, p: ScenarioParams) -> SimulationResult:
        monthly_exp      = snap.monthly_income_inr * 0.50
        extra_monthly    = monthly_exp * p.inflation_pct
        annual_extra     = extra_monthly * 12
        liquid_after     = snap.total_liquid_inr - annual_extra
        nw_after         = snap.net_worth_inr - annual_extra

        findings = [
            f"Inflation spike: +{p.inflation_pct:.0%} on expenses",
            f"Extra monthly cost: ₹{extra_monthly:,.0f}",
            f"Annual impact: ₹{annual_extra/1e5:.1f}L",
            f"Real return on FD reduced by {p.inflation_pct:.0%}",
        ]
        recs = [
            "Shift FD to debt MF for better post-tax returns",
            "Increase SIP by inflation rate annually",
            "Review expenses — cut discretionary spend",
        ]
        score = max(0, liquid_after) / max(1, snap.total_liquid_inr)
        ret_prob = self._monte_carlo_retirement(
            snap, p, inflation_shock=p.inflation_pct
        )
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Inflation spike +{p.inflation_pct:.0%}",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = nw_after,
            net_worth_impact_inr      = -annual_extra,
            net_worth_impact_pct      = -annual_extra / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = max(0, liquid_after),
            liquidity_impact_inr      = -annual_extra,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = None,
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_early_retirement(self, snap, p: ScenarioParams) -> SimulationResult:
        ret_goals = [
            g for g in snap.financial_goals
            if g.goal_type.value == "retirement"
        ]
        if not ret_goals:
            years_remaining = max(1, 60 - snap.age)
            target          = snap.monthly_income_inr * 12 * 20
        else:
            years_remaining = ret_goals[0].years_remaining
            target          = ret_goals[0].target_amount_inr

        new_years  = max(1, years_remaining - p.retire_years_earlier)
        sip        = sum(
            g.monthly_sip_inr for g in snap.financial_goals
        ) or snap.monthly_income_inr * 0.15
        savings    = sum(
            g.current_savings_inr for g in snap.financial_goals
        )

        fv_original = _future_value(savings, sip, years_remaining)
        fv_early    = _future_value(savings, sip, new_years)
        gap         = max(0, target - fv_early)
        impact      = fv_original - fv_early

        ret_prob_original = self._monte_carlo_retirement(snap, p)
        params_early      = ScenarioParams(
            scenario_type         = p.scenario_type,
            retire_years_earlier  = p.retire_years_earlier,
            monte_carlo_runs      = p.monte_carlo_runs,
        )
        # Adjust SIP for early run
        ret_prob_early = max(
            0,
            ret_prob_original - p.retire_years_earlier * 5
        )

        findings = [
            f"Retiring {p.retire_years_earlier}yr earlier: "
            f"at age {snap.age + new_years}",
            f"Corpus at original plan: ₹{fv_original/1e7:.2f}Cr",
            f"Corpus at early retire : ₹{fv_early/1e7:.2f}Cr",
            f"Shortfall              : ₹{gap/1e7:.2f}Cr",
        ]
        recs = []
        if gap > 0:
            needed_sip = _required_sip_calc(target - savings, new_years)
            recs.append(
                f"Need SIP of ₹{needed_sip:,.0f}/mo to retire early"
            )
            recs.append(
                f"Current SIP ₹{sip:,.0f} insufficient by "
                f"₹{needed_sip - sip:,.0f}/mo"
            )
        else:
            recs.append("Corpus sufficient for early retirement")
            recs.append("Review withdrawal strategy and tax impact")

        score = min(1.0, fv_early / max(1, target))
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Early retirement -{p.retire_years_earlier}yr",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = snap.net_worth_inr,
            net_worth_impact_inr      = -impact,
            net_worth_impact_pct      = -impact / max(1, fv_original),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = snap.total_liquid_inr,
            liquidity_impact_inr      = 0,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob_early,
            months_to_recovery        = None,
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_salary_growth(self, snap, p: ScenarioParams) -> SimulationResult:
        years          = 5
        future_income  = snap.monthly_income_inr * (
            (1 + p.annual_growth_pct) ** years
        )
        income_gain    = (future_income - snap.monthly_income_inr) * 12 * years
        nw_after       = snap.net_worth_inr + income_gain * 0.30
        ret_prob       = self._monte_carlo_retirement(
            snap, p, income_growth=p.annual_growth_pct
        )
        findings = [
            f"Income grows at {p.annual_growth_pct:.0%} p.a. for {years}yr",
            f"Monthly income: ₹{snap.monthly_income_inr/1e3:.0f}K → "
            f"₹{future_income/1e3:.0f}K",
            f"Additional wealth potential: ₹{income_gain*0.30/1e7:.2f}Cr",
        ]
        recs = [
            "Increase SIP by salary growth rate annually",
            "Max out 80C/NPS as income grows",
            "Review life cover — increases with income",
        ]
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Salary growth +{p.annual_growth_pct:.0%}/yr",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = nw_after,
            net_worth_impact_inr      = income_gain * 0.30,
            net_worth_impact_pct      = income_gain * 0.30 / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = snap.total_liquid_inr,
            liquidity_impact_inr      = 0,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = None,
            risk_level                = RiskLevel.LOW,
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_large_expense(self, snap, p: ScenarioParams) -> SimulationResult:
        liquid_after = snap.total_liquid_inr - p.expense_inr
        nw_after     = snap.net_worth_inr - p.expense_inr
        monthly_exp  = snap.monthly_income_inr * 0.50
        emergency    = monthly_exp * settings.emergency_fund_months

        findings = [
            f"Large expense: ₹{p.expense_inr/1e5:.1f}L",
            f"Liquid before: ₹{snap.total_liquid_inr/1e5:.1f}L",
            f"Liquid after : ₹{max(0,liquid_after)/1e5:.1f}L",
            f"Emergency fund "
            f"{'intact' if liquid_after >= emergency else 'BREACHED'}",
        ]
        recs = []
        if liquid_after < 0:
            recs.append("Fund from equity redemption — lowest return first")
            recs.append("Avoid personal loan — high interest cost")
        elif liquid_after < emergency:
            recs.append("Rebuild emergency fund over next 6 months")
            recs.append("Pause new investments temporarily")
        else:
            recs.append("Sufficient funds available — proceed")
            recs.append("Replenish used savings within 3 months")

        score = max(0, liquid_after) / max(1, snap.total_liquid_inr)
        ret_prob = self._monte_carlo_retirement(snap, p)
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Large expense ₹{p.expense_inr/1e5:.0f}L",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = nw_after,
            net_worth_impact_inr      = -p.expense_inr,
            net_worth_impact_pct      = -p.expense_inr / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = max(0, liquid_after),
            liquidity_impact_inr      = -p.expense_inr,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = int(
                p.expense_inr / max(1, snap.monthly_income_inr * 0.20)
            ),
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    def _sim_property_purchase(self, snap, p: ScenarioParams) -> SimulationResult:
        down_payment   = p.property_price_inr * p.down_payment_pct
        loan_amount    = p.property_price_inr - down_payment
        emi            = _emi_calc(loan_amount, 0.0875, 240)
        liquid_after   = snap.total_liquid_inr - down_payment
        new_foir       = (
            snap.monthly_emi_outflow_inr + emi
        ) / max(1, snap.monthly_income_inr)

        findings = [
            f"Property: ₹{p.property_price_inr/1e7:.1f}Cr",
            f"Down payment (20%): ₹{down_payment/1e5:.0f}L",
            f"Loan: ₹{loan_amount/1e7:.1f}Cr @ 8.75% for 20yr",
            f"EMI: ₹{emi:,.0f}/month",
            f"New FOIR: {new_foir:.0%} "
            f"({'OK' if new_foir <= settings.max_foir_pct else 'BREACH'})",
        ]
        recs = []
        if liquid_after < 0:
            recs.append(
                f"Insufficient funds — need ₹{-liquid_after/1e5:.0f}L more"
            )
            recs.append("Save for 12-18 more months before buying")
        elif new_foir > settings.max_foir_pct:
            recs.append(f"FOIR {new_foir:.0%} exceeds 50% — reduce loan")
            recs.append("Increase down payment or choose lower price")
        else:
            recs.append("Financially feasible — proceed with planning")
            recs.append("Claim 80C (principal) + 24b (interest) deductions")

        score = max(0, 1.0 - new_foir)
        ret_prob = self._monte_carlo_retirement(snap, p)
        return SimulationResult(
            scenario_type             = p.scenario_type,
            scenario_label            = f"Buy ₹{p.property_price_inr/1e7:.1f}Cr property",
            user_id                   = snap.user_id,
            net_worth_before_inr      = snap.net_worth_inr,
            net_worth_after_inr       = snap.net_worth_inr + (
                p.property_price_inr - down_payment * 0.5
            ),
            net_worth_impact_inr      = p.property_price_inr - loan_amount,
            net_worth_impact_pct      = (
                p.property_price_inr - loan_amount
            ) / max(1, snap.net_worth_inr),
            liquidity_before_inr      = snap.total_liquid_inr,
            liquidity_after_inr       = max(0, liquid_after),
            liquidity_impact_inr      = -down_payment,
            portfolio_drawdown_pct    = 0.0,
            retirement_probability_pct= ret_prob,
            months_to_recovery        = None,
            risk_level                = _risk_level(score),
            findings                  = findings,
            recommendations           = recs,
            monte_carlo_runs          = p.monte_carlo_runs,
        )

    # ── Monte Carlo ───────────────────────────────────────────────

    def _monte_carlo_retirement(
        self,
        snap,
        p: ScenarioParams,
        shock: float = 0.0,
        income_gap_months: int = 0,
        inflation_shock: float = 0.0,
        income_growth: float = 0.0,
    ) -> float:
        """
        Monte Carlo simulation for retirement probability.
        Returns % of runs where corpus >= target.
        """
        ret_goals = [
            g for g in snap.financial_goals
            if g.goal_type.value == "retirement"
        ]
        if not ret_goals:
            years  = max(1, 60 - snap.age)
            target = snap.monthly_income_inr * 12 * 20
            sip    = snap.monthly_income_inr * 0.15
            savings= 0
        else:
            g      = ret_goals[0]
            years  = max(1, g.years_remaining)
            target = g.target_amount_inr
            sip    = g.monthly_sip_inr
            savings= g.current_savings_inr

        # Adjust SIP for income gap
        effective_sip = sip * max(
            0, 1 - income_gap_months / max(1, years * 12)
        )

        # Mean annual return — shocked
        mean_return = 0.10 + shock + income_growth * 0.02
        std_return  = 0.12

        successes = 0
        rng = random.Random(42)  # deterministic seed for reproducibility

        for _ in range(p.monte_carlo_runs):
            corpus = savings * (1 + shock)
            monthly_sip = effective_sip
            for yr in range(years):
                annual_return = rng.gauss(mean_return, std_return)
                monthly_r     = (1 + annual_return) ** (1/12) - 1
                # Grow existing corpus
                corpus = corpus * (1 + annual_return)
                # Add SIP contributions
                corpus += monthly_sip * 12 * (
                    1 + annual_return * 0.5
                )
                # Income growth raises SIP
                monthly_sip *= (1 + income_growth)
                # Inflation reduces real value
                corpus /= (1 + (0.06 + inflation_shock))

            if corpus >= target:
                successes += 1

        return round(successes / p.monte_carlo_runs * 100, 1)


# ── Math helpers ─────────────────────────────────────────────────────

def _emi_calc(principal: float, rate: float, months: int) -> float:
    if months == 0 or principal == 0:
        return 0
    r = rate / 12
    return principal * r * (1 + r)**months / ((1 + r)**months - 1)


def _emi_increase(
    outstanding: float, rate_delta: float, months: int
) -> float:
    if months == 0:
        return 0
    new_emi = _emi_calc(outstanding, 0.0875 + rate_delta, months)
    old_emi = _emi_calc(outstanding, 0.0875, months)
    return max(0, new_emi - old_emi)


def _future_value(
    savings: float, monthly_sip: float, years: int
) -> float:
    if years <= 0:
        return savings
    r  = 0.10 / 12
    n  = years * 12
    fv = savings * ((1 + 0.10) ** years)
    fv += monthly_sip * (((1 + r)**n - 1) / r) * (1 + r)
    return fv


def _months_to_recover(
    loss: float, monthly_sip: float, annual_return: float
) -> Optional[int]:
    if monthly_sip <= 0:
        return None
    monthly_r = annual_return / 12
    recovered = 0
    months    = 0
    while recovered < loss and months < 360:
        recovered = recovered * (1 + monthly_r) + monthly_sip
        months   += 1
    return months if months < 360 else None


def _required_sip_calc(corpus: float, years: int) -> float:
    if years <= 0:
        return corpus
    r = 0.10 / 12
    n = years * 12
    return corpus * r / (((1 + r)**n - 1) * (1 + r))


def _default_scenarios() -> list[ScenarioParams]:
    return [
        ScenarioParams(ScenarioType.MARKET_CRASH,    drawdown_pct=0.30),
        ScenarioParams(ScenarioType.JOB_LOSS,         income_loss_months=6),
        ScenarioParams(ScenarioType.RATE_HIKE,        rate_hike_bps=200),
        ScenarioParams(ScenarioType.INFLATION_SPIKE,  inflation_pct=0.10),
        ScenarioParams(ScenarioType.EARLY_RETIREMENT, retire_years_earlier=5),
    ]
