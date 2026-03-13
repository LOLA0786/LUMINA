"""
LUMINA Financial Copilot
═════════════════════════
Natural language interface to the Financial OS.

Users ask questions. The copilot:
  1. Parses intent from natural language
  2. Routes to correct engine (simulation / score / agents)
  3. Runs the analysis
  4. Returns plain-English answer with numbers

Example conversations:

  User: "Can I retire at 45?"
  Copilot: Runs EARLY_RETIREMENT simulation → "At your current
           SIP of ₹15K/mo, you'll have ₹1.2Cr at 45 vs target
           ₹3Cr. You need ₹28K/mo SIP to retire at 45.
           Retirement probability: 34%."

  User: "What happens if market crashes 40%?"
  Copilot: Runs MARKET_CRASH simulation → "Your equity drops
           ₹8.1L. Emergency fund remains intact. Recovery
           estimated 14 months if SIP continues."

  User: "Should I buy a ₹1Cr house?"
  Copilot: Runs PROPERTY_PURCHASE simulation → "Down payment
           ₹20L — you have ₹35L liquid. EMI ₹78K raises your
           FOIR to 35% — within safe range. Feasible."

  User: "How is my portfolio?"
  Copilot: Runs ScoreEngine → "Your financial health is GOOD
           (70%). Portfolio drift is the main risk: equity at
           82% vs 66% target for age 34."

Behind the scenes:
  chat → IntentParser → engine router → result → NLG response

No LLM API required for core functionality.
Intent matching is rule-based + keyword scoring.
Optionally upgrades to LLM response generation.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.observability.logging import get_logger

logger = get_logger("lumina.copilot")


class CopilotIntent(str, Enum):
    # Simulation intents
    RETIRE_EARLY        = "retire_early"
    MARKET_CRASH        = "market_crash"
    JOB_LOSS            = "job_loss"
    BUY_PROPERTY        = "buy_property"
    LARGE_EXPENSE       = "large_expense"
    SALARY_GROWTH       = "salary_growth"
    RATE_HIKE           = "rate_hike"

    # Score / health intents
    HEALTH_CHECK        = "health_check"
    LIQUIDITY_CHECK     = "liquidity_check"
    PORTFOLIO_CHECK     = "portfolio_check"
    DEBT_CHECK          = "debt_check"
    RETIREMENT_CHECK    = "retirement_check"

    # Action intents
    INCREASE_SIP        = "increase_sip"
    REBALANCE           = "rebalance"
    TAX_OPTIMISE        = "tax_optimise"

    # Info intents
    NET_WORTH           = "net_worth"
    EXPLAIN_DECISION    = "explain_decision"

    # Fallback
    UNKNOWN             = "unknown"


@dataclass
class ParsedQuery:
    raw:            str
    intent:         CopilotIntent
    confidence:     float
    params:         dict[str, Any] = field(default_factory=dict)
    entities:       dict[str, Any] = field(default_factory=dict)


@dataclass
class CopilotResponse:
    query:          str
    intent:         str
    answer:         str
    numbers:        dict[str, Any]
    suggestions:    list[str]
    follow_ups:     list[str]
    latency_ms:     float
    engine_used:    str

    def render(self) -> str:
        lines = [
            "┌" + "─" * 56 + "┐",
            f"│  💬 {self.query[:50]:50}  │",
            "├" + "─" * 56 + "┤",
        ]
        for line in self.answer.split("\n"):
            while len(line) > 54:
                lines.append(f"│  {line[:54]}  │")
                line = line[54:]
            lines.append(f"│  {line:<54}  │")
        if self.numbers:
            lines.append("├" + "─" * 56 + "┤")
            for k, v in list(self.numbers.items())[:6]:
                lines.append(f"│  {k:28} {str(v):24}  │")
        if self.suggestions:
            lines.append("├" + "─" * 56 + "┤")
            lines.append(f"│  RECOMMENDATIONS{'':<39}  │")
            for s in self.suggestions[:3]:
                lines.append(f"│  → {s[:52]:52}  │")
        if self.follow_ups:
            lines.append("├" + "─" * 56 + "┤")
            lines.append(f"│  YOU MIGHT ALSO ASK{'':<36}  │")
            for f in self.follow_ups[:3]:
                lines.append(f"│  • {f[:52]:52}  │")
        lines.append(
            f"│  [{self.engine_used:20}  {self.latency_ms:.1f}ms]"
            f"{'':20}  │"
        )
        lines.append("└" + "─" * 56 + "┘")
        return "\n".join(lines)


class IntentParser:
    """
    Rule-based intent parser.
    Keyword scoring — no LLM required.
    Fast and deterministic.
    """

    PATTERNS: list[tuple[CopilotIntent, list[str], float]] = [
        # Retire early — high specificity
        (CopilotIntent.RETIRE_EARLY, [
            "retire at", "retire early", "early retirement",
            "retire by", "stop working", "financial independence",
            "fire", "retire age",
        ], 0.90),

        # Market crash
        (CopilotIntent.MARKET_CRASH, [
            "market crash", "crash", "market fall",
            "portfolio drop", "nifty falls", "bear market",
            "sensex falls", "market correction",
        ], 0.88),

        # Job loss
        (CopilotIntent.JOB_LOSS, [
            "lose job", "job loss", "lose my job", "unemployed",
            "layoff", "laid off", "retrenchment", "no income",
            "lose income",
        ], 0.88),

        # Buy property
        (CopilotIntent.BUY_PROPERTY, [
            "buy house", "buy flat", "buy property", "buy home",
            "purchase house", "home loan", "buy apartment",
            "afford house", "afford flat",
        ], 0.88),

        # Large expense
        (CopilotIntent.LARGE_EXPENSE, [
            "big expense", "large expense", "spend", "wedding",
            "vacation", "travel", "medical", "car",
            "afford", "can i spend",
        ], 0.72),

        # Salary growth
        (CopilotIntent.SALARY_GROWTH, [
            "salary growth", "hike", "increment", "pay raise",
            "salary increase", "promotion", "better salary",
        ], 0.80),

        # Rate hike
        (CopilotIntent.RATE_HIKE, [
            "rate hike", "interest rate", "rbi rate",
            "emi increase", "rate increase", "repo rate",
        ], 0.82),

        # Health check
        (CopilotIntent.HEALTH_CHECK, [
            "how am i doing", "financial health", "health score",
            "how is my finance", "overall score", "financial status",
            "am i on track", "my score",
        ], 0.85),

        # Liquidity
        (CopilotIntent.LIQUIDITY_CHECK, [
            "emergency fund", "liquid", "cash", "savings",
            "how much cash", "liquidity",
        ], 0.80),

        # Portfolio
        (CopilotIntent.PORTFOLIO_CHECK, [
            "portfolio", "investments", "mutual fund", "equity",
            "stocks", "sip", "how are my investments",
        ], 0.80),

        # Debt
        (CopilotIntent.DEBT_CHECK, [
            "debt", "loan", "emi", "liability",
            "how much do i owe", "outstanding",
        ], 0.80),

        # Retirement check
        (CopilotIntent.RETIREMENT_CHECK, [
            "retirement", "retire at 60", "retirement corpus",
            "pension", "retirement savings", "retire comfortably",
        ], 0.80),

        # SIP
        (CopilotIntent.INCREASE_SIP, [
            "increase sip", "start sip", "sip amount",
            "invest more", "how much sip",
        ], 0.82),

        # Rebalance
        (CopilotIntent.REBALANCE, [
            "rebalance", "rebalancing", "portfolio drift",
            "allocation", "asset mix",
        ], 0.80),

        # Tax
        (CopilotIntent.TAX_OPTIMISE, [
            "tax", "save tax", "80c", "tax regime",
            "tax saving", "elss", "nps", "tax optimise",
            "reduce tax",
        ], 0.80),

        # Net worth
        (CopilotIntent.NET_WORTH, [
            "net worth", "total wealth", "how much do i have",
            "total assets", "wealth",
        ], 0.82),
    ]

    def parse(self, query: str) -> ParsedQuery:
        q_lower = query.lower().strip()

        best_intent     = CopilotIntent.UNKNOWN
        best_confidence = 0.0

        for intent, keywords, base_conf in self.PATTERNS:
            matches = sum(1 for kw in keywords if kw in q_lower)
            if matches > 0:
                conf = min(1.0, base_conf + (matches - 1) * 0.05)
                if conf > best_confidence:
                    best_confidence = conf
                    best_intent     = intent

        # Extract numeric entities
        entities = {}
        amounts = re.findall(r'₹?\s*(\d+(?:\.\d+)?)\s*(?:cr|crore|l|lakh|k)?', q_lower)
        if amounts:
            entities["amounts"] = amounts

        age_match = re.search(r'\b(3\d|4\d|5\d|6\d)\b', q_lower)
        if age_match:
            entities["age"] = int(age_match.group(1))

        pct_match = re.search(r'(\d+)\s*(?:%|percent)', q_lower)
        if pct_match:
            entities["pct"] = int(pct_match.group(1))

        params = self._extract_params(best_intent, q_lower, entities)

        return ParsedQuery(
            raw        = query,
            intent     = best_intent,
            confidence = best_confidence,
            params     = params,
            entities   = entities,
        )

    def _extract_params(
        self,
        intent: CopilotIntent,
        q:      str,
        entities: dict,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if intent == CopilotIntent.RETIRE_EARLY:
            age = entities.get("age")
            if age:
                params["retire_age"] = age

        if intent == CopilotIntent.MARKET_CRASH:
            pct = entities.get("pct")
            params["drawdown_pct"] = (pct / 100) if pct else 0.30

        if intent == CopilotIntent.BUY_PROPERTY:
            amounts = entities.get("amounts", [])
            if amounts:
                val = float(amounts[0])
                if "cr" in q or "crore" in q:
                    val *= 1e7
                elif "l" in q or "lakh" in q:
                    val *= 1e5
                params["property_price_inr"] = val

        if intent == CopilotIntent.LARGE_EXPENSE:
            amounts = entities.get("amounts", [])
            if amounts:
                val = float(amounts[0])
                if "cr" in q or "crore" in q:
                    val *= 1e7
                elif "l" in q or "lakh" in q:
                    val *= 1e5
                elif "k" in q:
                    val *= 1e3
                params["expense_inr"] = val

        if intent == CopilotIntent.JOB_LOSS:
            months_match = re.search(r'(\d+)\s*month', q)
            params["income_loss_months"] = (
                int(months_match.group(1)) if months_match else 6
            )

        if intent == CopilotIntent.RATE_HIKE:
            bps_match = re.search(r'(\d+)\s*(?:bps|basis)', q)
            pct = entities.get("pct")
            if bps_match:
                params["rate_hike_bps"] = int(bps_match.group(1))
            elif pct:
                params["rate_hike_bps"] = pct * 100
            else:
                params["rate_hike_bps"] = 200

        return params


class FinancialCopilot:
    """
    Main copilot entry point.

    Usage:
        copilot = FinancialCopilot(financial_os)
        response = copilot.chat("vikram_nair", "Can I retire at 45?")
        print(response.render())

    Routes queries to:
        SimulationEngine  — what-if scenarios
        ScoreEngine       — health / dimension checks
        FinancialTwin     — net worth / asset queries
        AgentPlanner      — advice queries
    """

    def __init__(self, financial_os):
        self._os     = financial_os
        self._parser = IntentParser()
        from lumina.packages.decision_engine.decision_score import ScoreEngine
        from lumina.packages.simulation.simulation_engine import SimulationEngine
        self._score_engine = ScoreEngine()
        self._sim_engine   = SimulationEngine()

    def chat(self, user_id: str, query: str) -> CopilotResponse:
        start = time.perf_counter()

        parsed = self._parser.parse(query)
        logger.info(
            "copilot.query",
            user_id    = user_id,
            intent     = parsed.intent.value,
            confidence = parsed.confidence,
        )

        session = self._os._sessions.get(user_id)
        if not session:
            return self._error_response(
                query, "User not found. Please onboard first."
            )

        twin = session.twin
        response = self._route(query, parsed, twin)

        latency = (time.perf_counter() - start) * 1000
        response.latency_ms = latency

        logger.info(
            "copilot.response",
            user_id    = user_id,
            intent     = parsed.intent.value,
            engine     = response.engine_used,
            latency_ms = round(latency, 2),
        )
        return response

    def _route(
        self,
        query:  str,
        parsed: ParsedQuery,
        twin,
    ) -> CopilotResponse:
        intent = parsed.intent
        snap   = twin.current

        # ── Simulation intents ────────────────────────────────────
        if intent == CopilotIntent.RETIRE_EARLY:
            return self._handle_retire_early(query, parsed, snap, twin)

        if intent == CopilotIntent.MARKET_CRASH:
            return self._handle_market_crash(query, parsed, snap, twin)

        if intent == CopilotIntent.JOB_LOSS:
            return self._handle_job_loss(query, parsed, snap, twin)

        if intent == CopilotIntent.BUY_PROPERTY:
            return self._handle_property(query, parsed, snap, twin)

        if intent == CopilotIntent.LARGE_EXPENSE:
            return self._handle_expense(query, parsed, snap, twin)

        if intent == CopilotIntent.SALARY_GROWTH:
            return self._handle_salary_growth(query, parsed, snap, twin)

        if intent == CopilotIntent.RATE_HIKE:
            return self._handle_rate_hike(query, parsed, snap, twin)

        # ── Score intents ─────────────────────────────────────────
        if intent == CopilotIntent.HEALTH_CHECK:
            return self._handle_health(query, snap, twin)

        if intent == CopilotIntent.LIQUIDITY_CHECK:
            return self._handle_liquidity(query, snap)

        if intent == CopilotIntent.PORTFOLIO_CHECK:
            return self._handle_portfolio(query, snap)

        if intent == CopilotIntent.DEBT_CHECK:
            return self._handle_debt(query, snap)

        if intent == CopilotIntent.RETIREMENT_CHECK:
            return self._handle_retirement(query, snap, twin)

        # ── Info intents ──────────────────────────────────────────
        if intent == CopilotIntent.NET_WORTH:
            return self._handle_net_worth(query, snap)

        if intent == CopilotIntent.TAX_OPTIMISE:
            return self._handle_tax(query, snap)

        if intent == CopilotIntent.INCREASE_SIP:
            return self._handle_sip(query, snap)

        # ── Fallback ──────────────────────────────────────────────
        return self._handle_unknown(query, snap)

    # ── Simulation handlers ───────────────────────────────────────

    def _handle_retire_early(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        retire_age  = parsed.params.get("retire_age", 45)
        years_early = max(1, (60 - retire_age))
        params = ScenarioParams(
            scenario_type        = ScenarioType.EARLY_RETIREMENT,
            retire_years_earlier = years_early,
            monte_carlo_runs     = 1000,
        )
        result = self._sim_engine.run(twin, params)
        nw     = result.net_worth_before_inr
        impact = result.net_worth_impact_inr

        answer = (
            f"Retiring at {retire_age} means "
            f"{years_early} fewer years of compounding.\n"
            f"Projected corpus: "
            f"₹{(nw + impact)/1e7:.2f}Cr vs target.\n"
            f"Retirement probability: "
            f"{result.retirement_probability_pct:.0f}%.\n"
            f"{result.findings[2] if len(result.findings)>2 else ''}"
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Retire age":        retire_age,
                "Corpus projected":  f"₹{(nw+impact)/1e7:.2f}Cr",
                "Retire probability":f"{result.retirement_probability_pct:.0f}%",
                "Risk level":        result.risk_level.value,
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "What SIP do I need to retire at 45?",
                "What if market crashes before I retire?",
                "How much corpus do I need for ₹1L/month?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    def _handle_market_crash(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        drawdown = parsed.params.get("drawdown_pct", 0.30)
        params   = ScenarioParams(
            scenario_type = ScenarioType.MARKET_CRASH,
            drawdown_pct  = drawdown,
            monte_carlo_runs = 500,
        )
        result = self._sim_engine.run(twin, params)
        answer = (
            f"In a {drawdown:.0%} market crash:\n"
            f"Your portfolio loses "
            f"₹{abs(result.net_worth_impact_inr)/1e5:.1f}L.\n"
            f"Liquidity after crash: "
            f"₹{result.liquidity_after_inr/1e5:.1f}L.\n"
            f"Estimated recovery: "
            f"{result.months_to_recovery or 'N/A'} months."
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Drawdown":          f"{drawdown:.0%}",
                "Portfolio loss":    f"₹{abs(result.net_worth_impact_inr)/1e5:.1f}L",
                "Liquidity after":   f"₹{result.liquidity_after_inr/1e5:.1f}L",
                "Recovery months":   result.months_to_recovery,
                "Retire probability":f"{result.retirement_probability_pct:.0f}%",
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "Should I increase SIP during a crash?",
                "Is my emergency fund enough?",
                "What if I lose my job in a crash?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    def _handle_job_loss(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        months = parsed.params.get("income_loss_months", 6)
        params = ScenarioParams(
            scenario_type      = ScenarioType.JOB_LOSS,
            income_loss_months = months,
            monte_carlo_runs   = 500,
        )
        result = self._sim_engine.run(twin, params)
        burn   = snap.monthly_income_inr * 0.50 + snap.monthly_emi_outflow_inr
        runway = int(snap.total_liquid_inr / burn) if burn > 0 else 0
        answer = (
            f"If you lose income for {months} months:\n"
            f"Monthly burn rate: ₹{burn/1e3:.0f}K "
            f"(expenses + EMI).\n"
            f"Your cash runway: {runway} months.\n"
            f"{'You are covered.' if runway >= months else 'Runway is SHORT — act now.'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Income gap months": months,
                "Monthly burn":      f"₹{burn/1e3:.0f}K",
                "Cash runway":       f"{runway} months",
                "Liquid after":      f"₹{result.liquidity_after_inr/1e5:.1f}L",
                "Risk level":        result.risk_level.value,
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "How do I build a 9-month emergency fund?",
                "Should I reduce my EMI exposure?",
                "What's my minimum monthly survival amount?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    def _handle_property(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        price  = parsed.params.get("property_price_inr", 10_000_000)
        params = ScenarioParams(
            scenario_type      = ScenarioType.PROPERTY_PURCHASE,
            property_price_inr = price,
            down_payment_pct   = 0.20,
            monte_carlo_runs   = 500,
        )
        result = self._sim_engine.run(twin, params)
        dp     = price * 0.20
        answer = (
            f"Buying a ₹{price/1e7:.1f}Cr property:\n"
            f"Down payment needed: ₹{dp/1e5:.0f}L.\n"
            f"You currently have: "
            f"₹{snap.total_liquid_inr/1e5:.0f}L liquid.\n"
            f"{'Feasible.' if result.liquidity_after_inr >= 0 else 'Insufficient funds right now.'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Property price":  f"₹{price/1e7:.1f}Cr",
                "Down payment":    f"₹{dp/1e5:.0f}L",
                "Liquid now":      f"₹{snap.total_liquid_inr/1e5:.0f}L",
                "Liquid after":    f"₹{result.liquidity_after_inr/1e5:.1f}L",
                "Risk level":      result.risk_level.value,
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "What EMI will I pay on a ₹80L loan?",
                "Should I buy or continue renting?",
                "How much down payment should I save?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    def _handle_expense(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        expense = parsed.params.get("expense_inr", 500_000)
        params  = ScenarioParams(
            scenario_type = ScenarioType.LARGE_EXPENSE,
            expense_inr   = expense,
            monte_carlo_runs = 300,
        )
        result  = self._sim_engine.run(twin, params)
        answer  = (
            f"Spending ₹{expense/1e5:.1f}L:\n"
            f"Liquid before: ₹{snap.total_liquid_inr/1e5:.1f}L.\n"
            f"Liquid after: ₹{result.liquidity_after_inr/1e5:.1f}L.\n"
            f"{result.findings[-1] if result.findings else ''}"
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Expense":         f"₹{expense/1e5:.1f}L",
                "Liquid before":   f"₹{snap.total_liquid_inr/1e5:.1f}L",
                "Liquid after":    f"₹{result.liquidity_after_inr/1e5:.1f}L",
                "Risk level":      result.risk_level.value,
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "How long to rebuild savings after this?",
                "Should I use EMI instead of lump sum?",
                "Will this affect my retirement?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    def _handle_salary_growth(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        pct    = parsed.entities.get("pct", 10)
        params = ScenarioParams(
            scenario_type      = ScenarioType.SALARY_GROWTH,
            annual_growth_pct  = pct / 100,
            monte_carlo_runs   = 500,
        )
        result = self._sim_engine.run(twin, params)
        answer = (
            f"With {pct}% annual salary growth:\n"
            f"{result.findings[0] if result.findings else ''}\n"
            f"Retirement probability improves to "
            f"{result.retirement_probability_pct:.0f}%."
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Growth rate":       f"{pct}% p.a.",
                "NW impact 5yr":     f"₹{result.net_worth_impact_inr/1e7:.2f}Cr",
                "Retire probability":f"{result.retirement_probability_pct:.0f}%",
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "How much SIP should I add from the hike?",
                "Should I increase term cover with salary?",
                "What's the tax impact of higher income?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    def _handle_rate_hike(
        self, query, parsed, snap, twin
    ) -> CopilotResponse:
        from lumina.packages.simulation.simulation_engine import (
            ScenarioParams, ScenarioType,
        )
        bps    = parsed.params.get("rate_hike_bps", 200)
        params = ScenarioParams(
            scenario_type = ScenarioType.RATE_HIKE,
            rate_hike_bps = bps,
            monte_carlo_runs = 300,
        )
        result = self._sim_engine.run(twin, params)
        answer = (
            f"With a +{bps}bps rate hike:\n"
            f"{result.findings[1] if len(result.findings)>1 else ''}\n"
            f"{result.findings[2] if len(result.findings)>2 else ''}"
        )
        return CopilotResponse(
            query       = query,
            intent      = parsed.intent.value,
            answer      = answer,
            numbers     = {
                "Rate hike":        f"+{bps}bps",
                "Extra EMI/month":  result.findings[1][:30] if len(result.findings)>1 else "N/A",
                "NW impact":        f"₹{abs(result.net_worth_impact_inr)/1e5:.1f}L",
                "Risk level":       result.risk_level.value,
            },
            suggestions = result.recommendations,
            follow_ups  = [
                "Should I switch to a fixed rate loan?",
                "How much should I prepay on my loan?",
                "Will my FOIR breach 50%?",
            ],
            latency_ms  = 0,
            engine_used = "SimulationEngine",
        )

    # ── Score handlers ────────────────────────────────────────────

    def _handle_health(self, query, snap, twin) -> CopilotResponse:
        score  = self._score_engine.compute(twin)
        top_issue = next(
            (d for d in score.dimensions if d.action_needed), None
        )
        answer = (
            f"Your financial health is "
            f"{score.overall_band.value} "
            f"({score.overall_score:.0%}).\n"
            + (
                f"Biggest gap: {top_issue.name} — "
                f"{top_issue.insight}"
                if top_issue else "All dimensions look healthy."
            )
        )
        return CopilotResponse(
            query       = query,
            intent      = "health_check",
            answer      = answer,
            numbers     = {
                d.name: f"{d.score:.0%} ({d.band.value})"
                for d in score.dimensions
            },
            suggestions = [
                d.recommended_action
                for d in score.dimensions
                if d.recommended_action
            ][:3],
            follow_ups  = [
                "What's my biggest financial risk?",
                "How do I improve my liquidity score?",
                "Am I on track for retirement?",
            ],
            latency_ms  = 0,
            engine_used = "ScoreEngine",
        )

    def _handle_liquidity(self, query, snap) -> CopilotResponse:
        monthly_exp   = snap.monthly_income_inr * 0.50
        emergency     = monthly_exp * 6
        liquid        = snap.total_liquid_inr
        months_covered= int(liquid / monthly_exp) if monthly_exp > 0 else 0
        answer = (
            f"You have ₹{liquid/1e5:.1f}L in liquid assets.\n"
            f"That covers {months_covered} months of expenses.\n"
            f"Recommended: 6 months = ₹{emergency/1e5:.1f}L.\n"
            f"{'You are covered.' if liquid >= emergency else f'Shortfall: ₹{(emergency-liquid)/1e5:.1f}L.'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = "liquidity_check",
            answer      = answer,
            numbers     = {
                "Liquid assets":    f"₹{liquid/1e5:.1f}L",
                "Months covered":   months_covered,
                "Target (6mo)":     f"₹{emergency/1e5:.1f}L",
                "Shortfall":        f"₹{max(0,emergency-liquid)/1e5:.1f}L",
            },
            suggestions = [
                "Move surplus to liquid mutual fund",
                "Avoid locking liquid savings in FDs > 1yr",
            ] if liquid < emergency else [
                "Emergency fund adequate — no action needed",
            ],
            follow_ups  = [
                "What happens if I lose my job?",
                "Where should I keep my emergency fund?",
                "How do I build ₹5L in 6 months?",
            ],
            latency_ms  = 0,
            engine_used = "FinancialTwin",
        )

    def _handle_portfolio(self, query, snap) -> CopilotResponse:
        equity_val = sum(
            h.current_value_inr for h in snap.demat_holdings
        )
        target_eq  = max(0.20, min(0.80, (100 - snap.age) / 100))
        total      = snap.total_assets_inr
        eq_pct     = equity_val / total if total else 0
        answer = (
            f"Total investments: ₹{equity_val/1e5:.1f}L.\n"
            f"Equity allocation: {eq_pct:.0%} "
            f"(target for age {snap.age}: {target_eq:.0%}).\n"
            f"Drift: {abs(eq_pct - target_eq):.0%} — "
            f"{'rebalance recommended' if abs(eq_pct-target_eq)>0.10 else 'within range'}."
        )
        return CopilotResponse(
            query       = query,
            intent      = "portfolio_check",
            answer      = answer,
            numbers     = {
                "Portfolio value":  f"₹{equity_val/1e5:.1f}L",
                "Equity %":         f"{eq_pct:.0%}",
                "Target equity %":  f"{target_eq:.0%}",
                "Drift":            f"{abs(eq_pct-target_eq):.0%}",
            },
            suggestions = [
                "Rebalance equity to target allocation",
                "Add debt MF to reduce concentration",
            ] if abs(eq_pct - target_eq) > 0.10 else [
                "Portfolio well-allocated — continue SIP",
            ],
            follow_ups  = [
                "Should I rebalance my portfolio now?",
                "What funds should I add?",
                "What happens in a 30% crash?",
            ],
            latency_ms  = 0,
            engine_used = "FinancialTwin",
        )

    def _handle_debt(self, query, snap) -> CopilotResponse:
        emi    = snap.monthly_emi_outflow_inr
        income = snap.monthly_income_inr
        foir   = emi / income if income > 0 else 0
        total_debt = sum(l.outstanding_inr for l in snap.loans)
        answer = (
            f"Total outstanding debt: ₹{total_debt/1e5:.1f}L.\n"
            f"Monthly EMI: ₹{emi/1e3:.0f}K "
            f"({foir:.0%} of income).\n"
            f"FOIR limit: 50%. "
            f"{'You are within limit.' if foir <= 0.50 else 'BREACH — reduce debt urgently.'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = "debt_check",
            answer      = answer,
            numbers     = {
                "Total debt":     f"₹{total_debt/1e5:.1f}L",
                "Monthly EMI":    f"₹{emi/1e3:.0f}K",
                "FOIR":           f"{foir:.0%}",
                "FOIR limit":     "50%",
            },
            suggestions = [
                "Prepay highest interest loan first",
                "Avoid new loans until FOIR < 35%",
            ] if foir > 0.35 else [
                "Debt under control — maintain discipline",
            ],
            follow_ups  = [
                "Should I prepay my home loan?",
                "What if interest rates rise 2%?",
                "How quickly can I become debt-free?",
            ],
            latency_ms  = 0,
            engine_used = "FinancialTwin",
        )

    def _handle_retirement(self, query, snap, twin) -> CopilotResponse:
        score  = self._score_engine.compute(twin)
        ret_dim= next(
            (d for d in score.dimensions if d.name == "Retirement"),
            None,
        )
        answer = (
            f"Retirement score: "
            f"{ret_dim.score:.0%} ({ret_dim.band.value}).\n"
            + (ret_dim.insight if ret_dim else "No retirement goal set.")
            + f"\nKey metric: {ret_dim.key_metric if ret_dim else 'N/A'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = "retirement_check",
            answer      = answer,
            numbers     = {
                "Score":         f"{ret_dim.score:.0%}" if ret_dim else "N/A",
                "Band":          ret_dim.band.value if ret_dim else "N/A",
                "Key metric":    ret_dim.key_metric if ret_dim else "N/A",
            },
            suggestions = [ret_dim.recommended_action]
                          if ret_dim and ret_dim.recommended_action else [],
            follow_ups  = [
                "Can I retire at 50?",
                "What SIP do I need to retire at 60?",
                "What if market crashes before I retire?",
            ],
            latency_ms  = 0,
            engine_used = "ScoreEngine",
        )

    def _handle_net_worth(self, query, snap) -> CopilotResponse:
        answer = (
            f"Your net worth is ₹{snap.net_worth_inr/1e7:.2f}Cr.\n"
            f"Assets: ₹{snap.total_assets_inr/1e7:.2f}Cr | "
            f"Liabilities: ₹{snap.total_liabilities_inr/1e5:.0f}L.\n"
            f"Liquid: ₹{snap.total_liquid_inr/1e5:.1f}L."
        )
        return CopilotResponse(
            query       = query,
            intent      = "net_worth",
            answer      = answer,
            numbers     = {
                "Net worth":    f"₹{snap.net_worth_inr/1e7:.2f}Cr",
                "Total assets": f"₹{snap.total_assets_inr/1e7:.2f}Cr",
                "Liabilities":  f"₹{snap.total_liabilities_inr/1e5:.0f}L",
                "Liquid":       f"₹{snap.total_liquid_inr/1e5:.1f}L",
            },
            suggestions = [],
            follow_ups  = [
                "How does my net worth compare to my age?",
                "What is my biggest asset?",
                "How do I double my net worth in 7 years?",
            ],
            latency_ms  = 0,
            engine_used = "FinancialTwin",
        )

    def _handle_tax(self, query, snap) -> CopilotResponse:
        tax = snap.tax_profile
        answer = (
            f"Current regime: {tax.preferred_regime}.\n"
            f"80C used: ₹{tax.deductions_80c_inr/1e5:.1f}L "
            f"(limit ₹1.5L).\n"
            f"NPS 80CCD: ₹{tax.nps_80ccd_inr/1e3:.0f}K.\n"
            f"{'Maximise 80C — ₹{:.1f}L remaining.'.format((150000-tax.deductions_80c_inr)/1e5) if tax.deductions_80c_inr < 150000 else '80C fully utilised.'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = "tax_optimise",
            answer      = answer,
            numbers     = {
                "Regime":       tax.preferred_regime,
                "80C used":     f"₹{tax.deductions_80c_inr/1e5:.1f}L",
                "80C limit":    "₹1.5L",
                "NPS":          f"₹{tax.nps_80ccd_inr/1e3:.0f}K",
            },
            suggestions = [
                "Max out 80C via ELSS — best post-tax returns",
                "Add NPS for extra ₹50K deduction (80CCD1B)",
                "Compare old vs new regime with your deductions",
            ],
            follow_ups  = [
                "Old vs new tax regime — which is better for me?",
                "How do I save ₹1L in taxes?",
                "Should I invest in NPS?",
            ],
            latency_ms  = 0,
            engine_used = "FinancialTwin",
        )

    def _handle_sip(self, query, snap) -> CopilotResponse:
        current_sip = sum(
            g.monthly_sip_inr for g in snap.financial_goals
        )
        rec_sip     = snap.monthly_income_inr * 0.20
        answer = (
            f"Current SIP: ₹{current_sip/1e3:.0f}K/month.\n"
            f"Recommended (20% of income): "
            f"₹{rec_sip/1e3:.0f}K/month.\n"
            f"{'Increase by ₹{:.0f}K to hit target.'.format((rec_sip-current_sip)/1e3) if current_sip < rec_sip else 'You are investing above the 20% benchmark.'}"
        )
        return CopilotResponse(
            query       = query,
            intent      = "increase_sip",
            answer      = answer,
            numbers     = {
                "Current SIP":   f"₹{current_sip/1e3:.0f}K",
                "Recommended":   f"₹{rec_sip/1e3:.0f}K",
                "Gap":           f"₹{max(0,rec_sip-current_sip)/1e3:.0f}K",
            },
            suggestions = [
                f"Increase SIP by ₹{max(0,rec_sip-current_sip)/1e3:.0f}K/month",
                "Step-up SIP by 10% each April",
                "Route any bonus to lump sum top-up",
            ],
            follow_ups  = [
                "What corpus will my SIP build in 20 years?",
                "Which fund should I add my SIP to?",
                "What if I increase SIP by ₹5K now?",
            ],
            latency_ms  = 0,
            engine_used = "FinancialTwin",
        )

    def _handle_unknown(self, query, snap) -> CopilotResponse:
        return CopilotResponse(
            query       = query,
            intent      = "unknown",
            answer      = (
                "I didn't quite understand that. "
                "Try asking about your portfolio, "
                "retirement, liquidity, or a specific scenario "
                "like 'what if market crashes 30%?'"
            ),
            numbers     = {},
            suggestions = [],
            follow_ups  = [
                "How is my financial health?",
                "Can I retire at 50?",
                "What if market crashes 30%?",
                "How much is my net worth?",
            ],
            latency_ms  = 0,
            engine_used = "IntentParser",
        )

    def _error_response(self, query, message) -> CopilotResponse:
        return CopilotResponse(
            query       = query,
            intent      = "error",
            answer      = message,
            numbers     = {},
            suggestions = [],
            follow_ups  = [],
            latency_ms  = 0,
            engine_used = "none",
        )
