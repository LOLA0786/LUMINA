"""
LUMINA Decision Score System
══════════════════════════════
Every user gets a live financial health score
across 5 dimensions. Updated on every event.

Dimensions:
  1. LIQUIDITY     — emergency fund adequacy
  2. PORTFOLIO     — diversification + drift
  3. DEBT          — EMI/income ratio + interest burden
  4. PROTECTION    — insurance coverage adequacy
  5. RETIREMENT    — corpus projection vs target

Each dimension: 0.0 → 1.0
Overall score:  weighted composite

Score bands:
  0.80 - 1.00  EXCELLENT  (green)
  0.60 - 0.79  GOOD       (yellow-green)
  0.40 - 0.59  NEEDS WORK (yellow)
  0.20 - 0.39  AT RISK    (orange)
  0.00 - 0.19  CRITICAL   (red)

This becomes the core metric of LUMINA.
Every agent decision moves this score.
Advisors track it. Users obsess over it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.config.settings import settings
from lumina.observability.logging import get_logger

logger = get_logger("lumina.decision_score")


class ScoreBand(str, Enum):
    EXCELLENT  = "EXCELLENT"
    GOOD       = "GOOD"
    NEEDS_WORK = "NEEDS_WORK"
    AT_RISK    = "AT_RISK"
    CRITICAL   = "CRITICAL"


def score_to_band(score: float) -> ScoreBand:
    if score >= 0.80:
        return ScoreBand.EXCELLENT
    if score >= 0.60:
        return ScoreBand.GOOD
    if score >= 0.40:
        return ScoreBand.NEEDS_WORK
    if score >= 0.20:
        return ScoreBand.AT_RISK
    return ScoreBand.CRITICAL


def score_to_emoji(score: float) -> str:
    band = score_to_band(score)
    return {
        ScoreBand.EXCELLENT:  "🟢",
        ScoreBand.GOOD:       "🟡",
        ScoreBand.NEEDS_WORK: "🟠",
        ScoreBand.AT_RISK:    "🔴",
        ScoreBand.CRITICAL:   "🚨",
    }[band]


@dataclass
class DimensionScore:
    name: str
    score: float                        # 0.0 → 1.0
    band: ScoreBand
    weight: float                       # contribution to overall
    key_metric: str                     # human-readable metric
    insight: str                        # one-line explanation
    action_needed: bool = False
    recommended_action: Optional[str]   = None


@dataclass
class FinancialHealthScore:
    """
    Complete financial health scorecard for a user.
    Computed fresh from the Digital Twin on every call.
    """
    user_id:          str
    overall_score:    float
    overall_band:     ScoreBand
    dimensions:       list[DimensionScore]
    computed_at:      float = field(default_factory=time.time)
    snapshot_hash:    str   = ""
    delta_from_last:  Optional[float] = None   # score change since last

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":       self.user_id,
            "overall_score": round(self.overall_score, 3),
            "overall_band":  self.overall_band.value,
            "emoji":         score_to_emoji(self.overall_score),
            "computed_at":   self.computed_at,
            "snapshot_hash": self.snapshot_hash,
            "delta":         round(self.delta_from_last, 3)
                             if self.delta_from_last else None,
            "dimensions": [
                {
                    "name":               d.name,
                    "score":              round(d.score, 3),
                    "band":               d.band.value,
                    "weight":             d.weight,
                    "key_metric":         d.key_metric,
                    "insight":            d.insight,
                    "action_needed":      d.action_needed,
                    "recommended_action": d.recommended_action,
                }
                for d in self.dimensions
            ],
        }

    def render(self) -> str:
        lines = [
            "┌" + "─" * 54 + "┐",
            f"│  LUMINA FINANCIAL HEALTH SCORE"
            f"{'':22}│",
            f"│  User: {self.user_id:45}│",
            "├" + "─" * 54 + "┤",
            f"│  Overall:  {score_to_emoji(self.overall_score)} "
            f"{self.overall_band.value:12}"
            f"  {self.overall_score:.0%}{'':16}│",
        ]
        if self.delta_from_last is not None:
            arrow = "↑" if self.delta_from_last >= 0 else "↓"
            lines.append(
                f"│  Change:   {arrow} {abs(self.delta_from_last):.1%}"
                f" since last compute{'':13}│"
            )
        lines.append("├" + "─" * 54 + "┤")
        for d in self.dimensions:
            bar_filled = int(d.score * 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            flag = " ⚠" if d.action_needed else "  "
            lines.append(
                f"│{flag} {d.name:14} {bar} "
                f"{d.score:.0%}{'':3}│"
            )
            lines.append(
                f"│    {d.insight[:48]:48}  │"
            )
        lines.append("└" + "─" * 54 + "┘")
        return "\n".join(lines)


class ScoreEngine:
    """
    Computes FinancialHealthScore from a FinancialTwin snapshot.

    Weights:
      Liquidity   25%  — most critical for short-term safety
      Portfolio   25%  — wealth creation engine
      Debt        20%  — leverage risk
      Protection  15%  — insurance safety net
      Retirement  15%  — long-term outcome

    Each dimension uses financial rules from settings.
    """

    WEIGHTS = {
        "Liquidity":  0.25,
        "Portfolio":  0.25,
        "Debt":       0.20,
        "Protection": 0.15,
        "Retirement": 0.15,
    }

    def __init__(self):
        self._score_history: dict[str, list[float]] = {}

    def compute(self, twin) -> FinancialHealthScore:
        snap = twin.current
        dimensions = [
            self._score_liquidity(snap),
            self._score_portfolio(snap),
            self._score_debt(snap),
            self._score_protection(snap),
            self._score_retirement(snap),
        ]

        overall = sum(
            d.score * d.weight for d in dimensions
        )
        overall = max(0.0, min(1.0, overall))

        # Delta from last
        history = self._score_history.get(twin.user_id, [])
        delta   = (overall - history[-1]) if history else None
        history.append(overall)
        self._score_history[twin.user_id] = history[-10:]  # keep last 10

        score = FinancialHealthScore(
            user_id         = twin.user_id,
            overall_score   = overall,
            overall_band    = score_to_band(overall),
            dimensions      = dimensions,
            snapshot_hash   = snap.state_hash,
            delta_from_last = delta,
        )

        logger.info(
            "score.computed",
            user_id       = twin.user_id,
            overall       = round(overall, 3),
            band          = score.overall_band.value,
            delta         = round(delta, 3) if delta else None,
        )
        return score

    # ── Dimension scorers ─────────────────────────────────────────

    def _score_liquidity(self, snap) -> DimensionScore:
        monthly_exp    = snap.monthly_income_inr * 0.5
        emergency_fund = monthly_exp * settings.emergency_fund_months
        liquid         = snap.total_liquid_inr

        if emergency_fund == 0:
            ratio = 1.0
        else:
            ratio = min(1.0, liquid / emergency_fund)

        score = ratio
        action = ratio < 0.80

        if ratio >= 1.0:
            insight = (
                f"₹{liquid/1e5:.1f}L liquid — "
                f"{settings.emergency_fund_months}mo fund fully covered"
            )
            rec = None
        elif ratio >= 0.50:
            insight = (
                f"₹{liquid/1e5:.1f}L liquid — "
                f"need ₹{emergency_fund/1e5:.1f}L"
            )
            rec = f"Add ₹{(emergency_fund - liquid)/1e5:.1f}L to liquid savings"
        else:
            insight = (
                f"CRITICAL: only {ratio:.0%} of emergency fund built"
            )
            rec = "Pause investments. Build emergency fund first."

        return DimensionScore(
            name               = "Liquidity",
            score              = score,
            band               = score_to_band(score),
            weight             = self.WEIGHTS["Liquidity"],
            key_metric         = f"₹{liquid/1e5:.1f}L / ₹{emergency_fund/1e5:.1f}L",
            insight            = insight,
            action_needed      = action,
            recommended_action = rec,
        )

    def _score_portfolio(self, snap) -> DimensionScore:
        total  = snap.total_assets_inr
        if total == 0:
            return DimensionScore(
                name       = "Portfolio",
                score      = 0.0,
                band       = ScoreBand.CRITICAL,
                weight     = self.WEIGHTS["Portfolio"],
                key_metric = "No assets",
                insight    = "No investments found",
                action_needed      = True,
                recommended_action = "Start a ₹500/mo SIP immediately",
            )

        equity_val = sum(
            h.current_value_inr for h in snap.demat_holdings
            if h.holding_type.value in (
                "equity_mf", "etf", "stock"
            )
        )
        prop_val = sum(
            p.current_value_inr for p in snap.property_assets
        )
        equity_pct = equity_val / total
        prop_pct   = prop_val  / total

        # Age-adjusted equity target (100 - age rule)
        target_equity = max(0.20, min(0.80, (100 - snap.age) / 100))
        drift         = abs(equity_pct - target_equity)

        # Concentration penalty
        concentration_penalty = max(0.0, prop_pct - 0.60) * 2

        score = max(0.0, 1.0 - drift - concentration_penalty)

        if prop_pct > 0.70:
            insight = (
                f"Real estate {prop_pct:.0%} of portfolio — "
                "concentration risk"
            )
            rec = "Increase liquid investments to reduce concentration"
            action = True
        elif drift > 0.20:
            insight = (
                f"Equity {equity_pct:.0%} vs target {target_equity:.0%} "
                f"— drift {drift:.0%}"
            )
            rec = "Rebalance portfolio to target allocation"
            action = True
        else:
            insight = (
                f"Equity {equity_pct:.0%} ≈ target {target_equity:.0%} "
                "— well allocated"
            )
            rec    = None
            action = False

        return DimensionScore(
            name               = "Portfolio",
            score              = score,
            band               = score_to_band(score),
            weight             = self.WEIGHTS["Portfolio"],
            key_metric         = f"equity={equity_pct:.0%} target={target_equity:.0%}",
            insight            = insight,
            action_needed      = action,
            recommended_action = rec,
        )

    def _score_debt(self, snap) -> DimensionScore:
        monthly_emi    = snap.monthly_emi_outflow_inr
        monthly_income = snap.monthly_income_inr

        if monthly_income == 0:
            foir = 0.0
        else:
            foir = monthly_emi / monthly_income

        max_foir = settings.max_foir_pct
        score    = max(0.0, 1.0 - (foir / max_foir)) if foir > 0 else 1.0

        if foir == 0:
            insight = "Debt-free — full income available for wealth creation"
            rec     = None
            action  = False
        elif foir <= settings.comfortable_foir_pct:
            insight = (
                f"EMI/income ratio {foir:.0%} — "
                "within comfortable range"
            )
            rec    = None
            action = False
        elif foir <= max_foir:
            insight = (
                f"EMI/income ratio {foir:.0%} — "
                f"approaching limit ({max_foir:.0%})"
            )
            rec    = "Avoid new loans. Prepay high-interest debt first."
            action = True
        else:
            insight = (
                f"CRITICAL: EMI/income {foir:.0%} "
                f"exceeds safe limit {max_foir:.0%}"
            )
            rec    = "Immediate debt restructuring needed"
            action = True

        return DimensionScore(
            name               = "Debt",
            score              = score,
            band               = score_to_band(score),
            weight             = self.WEIGHTS["Debt"],
            key_metric         = f"FOIR={foir:.0%} limit={max_foir:.0%}",
            insight            = insight,
            action_needed      = action,
            recommended_action = rec,
        )

    def _score_protection(self, snap) -> DimensionScore:
        annual_income  = snap.monthly_income_inr * 12
        sum_assured    = sum(
            p.sum_assured_inr for p in snap.insurance_policies
            if p.policy_type == "term"
        )
        # Rule: life cover should be 10-15x annual income
        required_cover = annual_income * 12
        coverage_ratio = (
            sum_assured / required_cover
            if required_cover > 0 else 0.0
        )
        score  = min(1.0, coverage_ratio)
        gap    = max(0.0, required_cover - sum_assured)
        action = coverage_ratio < 0.80

        if coverage_ratio >= 1.0:
            insight = (
                f"Term cover ₹{sum_assured/1e7:.1f}Cr — "
                "adequately protected"
            )
            rec = None
        elif coverage_ratio > 0:
            insight = (
                f"Cover ₹{sum_assured/1e5:.0f}L — "
                f"gap ₹{gap/1e7:.1f}Cr"
            )
            rec = f"Top up term insurance by ₹{gap/1e7:.1f}Cr"
        else:
            insight = "No term insurance — family fully exposed"
            rec     = (
                f"Buy ₹{required_cover/1e7:.1f}Cr term plan immediately"
            )

        return DimensionScore(
            name               = "Protection",
            score              = score,
            band               = score_to_band(score),
            weight             = self.WEIGHTS["Protection"],
            key_metric         = (
                f"cover=₹{sum_assured/1e5:.0f}L "
                f"needed=₹{required_cover/1e7:.1f}Cr"
            ),
            insight            = insight,
            action_needed      = action,
            recommended_action = rec,
        )

    def _score_retirement(self, snap) -> DimensionScore:
        retirement_goals = [
            g for g in snap.financial_goals
            if g.goal_type.value == "retirement"
        ]
        if not retirement_goals:
            return DimensionScore(
                name               = "Retirement",
                score              = 0.30,
                band               = ScoreBand.AT_RISK,
                weight             = self.WEIGHTS["Retirement"],
                key_metric         = "No retirement goal set",
                insight            = "No retirement goal defined",
                action_needed      = True,
                recommended_action = "Set a retirement goal and start SIP",
            )

        goal    = retirement_goals[0]
        years   = goal.years_remaining
        monthly = snap.monthly_income_inr
        sip     = goal.monthly_sip_inr

        # Future value of current SIP at 10% p.a.
        if years > 0 and sip > 0:
            r   = 0.10 / 12
            n   = years * 12
            fv  = sip * (((1 + r) ** n - 1) / r) * (1 + r)
            fv += goal.current_savings_inr * ((1 + 0.10) ** years)
        else:
            fv = goal.current_savings_inr

        progress = min(1.0, fv / goal.target_amount_inr) if goal.target_amount_inr else 0
        score    = progress
        action   = progress < 0.70

        if progress >= 1.0:
            insight = (
                f"On track — projected ₹{fv/1e7:.1f}Cr "
                f"vs target ₹{goal.target_amount_inr/1e7:.1f}Cr"
            )
            rec = None
        elif progress >= 0.70:
            insight = (
                f"{progress:.0%} funded — "
                f"₹{(goal.target_amount_inr - fv)/1e5:.0f}L gap"
            )
            rec = "Increase SIP by 10% annually"
        else:
            needed_sip = _required_sip(
                goal.target_amount_inr - goal.current_savings_inr,
                years,
            )
            insight = (
                f"BEHIND: {progress:.0%} funded — "
                f"need ₹{needed_sip/1000:.0f}K/mo SIP"
            )
            rec = f"Increase SIP to ₹{needed_sip:,.0f}/month"

        return DimensionScore(
            name               = "Retirement",
            score              = score,
            band               = score_to_band(score),
            weight             = self.WEIGHTS["Retirement"],
            key_metric         = (
                f"projected=₹{fv/1e7:.1f}Cr "
                f"target=₹{goal.target_amount_inr/1e7:.1f}Cr"
            ),
            insight            = insight,
            action_needed      = action,
            recommended_action = rec,
        )


def _required_sip(corpus_needed: float, years: int) -> float:
    if years <= 0:
        return corpus_needed
    r = 0.10 / 12
    n = years * 12
    return corpus_needed * r / (((1 + r) ** n - 1) * (1 + r))
