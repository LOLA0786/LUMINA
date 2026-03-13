"""
LUMINA Multi-Agent Debate Engine
Agents don't run in isolation. They argue. Planner arbitrates.

Example — MARKET_CRASH fires on Rohan's portfolio:
  PortfolioAgent → REBALANCE  "equity drifted to 85%, reduce ₹3L"
  RiskAgent      → HOLD       "liquidity too low to sell now"
  RetirementAgent→ BUY_MORE   "26yr horizon, this is opportunity"

  Debate result: CONTESTED
  Winner (by priority weight): RiskAgent → HOLD
  Reason: liquidity concern outweighs rebalancing benefit
  Dissenting: PortfolioAgent, RetirementAgent

Priority: RiskAgent > RetirementAgent > PortfolioAgent > TaxAgent
"""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentPosition(str, Enum):
    STRONG_BUY        = "strong_buy"
    BUY               = "buy"
    HOLD              = "hold"
    REDUCE            = "reduce"
    STRONG_REDUCE     = "strong_reduce"
    REBALANCE         = "rebalance"
    ALERT_ONLY        = "alert_only"
    INSUFFICIENT_DATA = "insufficient_data"


class DebateVerdict(str, Enum):
    UNANIMOUS  = "unanimous"    # all agents agree
    MAJORITY   = "majority"     # >60% weighted agreement
    CONTESTED  = "contested"    # significant disagreement
    DEFERRED   = "deferred"     # confidence too low to act


@dataclass
class AgentArgument:
    agent_name: str
    position: AgentPosition
    reasoning: str
    confidence: float
    recommended_action: Optional[str] = None
    recommended_amount_inr: Optional[float] = None
    priority: int = 5           # 1=highest weight, 10=lowest


@dataclass
class DebateOutcome:
    debate_id: str               = field(default_factory=lambda: str(uuid.uuid4()))
    event_trigger: str           = ""
    user_id: str                 = ""
    timestamp: float             = field(default_factory=time.time)
    arguments: list              = field(default_factory=list)
    verdict: DebateVerdict       = DebateVerdict.DEFERRED
    winning_position: Optional[AgentPosition] = None
    final_recommendation: str    = ""
    final_confidence: float      = 0.0
    dissenting_agents: list      = field(default_factory=list)
    requires_user_approval: bool = True
    requires_governance_check: bool = True


class DebateEngine:
    """
    Arbitrates agent disagreements.
    Uses priority-weighted voting — not simple majority.
    RiskAgent always has the loudest voice.
    """

    PRIORITY_MAP = {
        "risk_agent":           1,
        "retirement_agent":     2,
        "portfolio_agent":      3,
        "tax_agent":            4,
        "house_purchase_agent": 5,
    }

    def arbitrate(
        self,
        arguments: list[AgentArgument],
        event_trigger: str,
        user_id: str,
    ) -> DebateOutcome:

        if not arguments:
            return DebateOutcome(event_trigger=event_trigger, user_id=user_id)

        # Sort by priority
        sorted_args = sorted(
            arguments,
            key=lambda a: self.PRIORITY_MAP.get(a.agent_name, 9),
        )

        # Weighted vote — higher priority agents carry more weight
        position_votes: dict[AgentPosition, float] = {}
        for arg in sorted_args:
            weight = 1.0 / self.PRIORITY_MAP.get(arg.agent_name, 9)
            position_votes[arg.position] = (
                position_votes.get(arg.position, 0) + weight * arg.confidence
            )

        winning_pos   = max(position_votes, key=position_votes.get)
        winning_weight = position_votes[winning_pos]
        total_weight   = sum(position_votes.values())
        agreement_ratio = winning_weight / total_weight if total_weight else 0

        if agreement_ratio >= 0.80:
            verdict = DebateVerdict.UNANIMOUS
        elif agreement_ratio >= 0.60:
            verdict = DebateVerdict.MAJORITY
        else:
            verdict = DebateVerdict.CONTESTED

        dissenters = [
            a.agent_name for a in sorted_args if a.position != winning_pos
        ]

        avg_confidence = sum(a.confidence for a in sorted_args) / len(sorted_args)
        final_confidence = (winning_weight / total_weight) * avg_confidence

        # Recommendation from highest-priority agent holding winning position
        primary = next(
            (a for a in sorted_args if a.position == winning_pos),
            sorted_args[0],
        )
        recommendation = (
            primary.recommended_action
            or winning_pos.value.replace("_", " ").title()
        )

        needs_approval = (
            verdict == DebateVerdict.CONTESTED
            or winning_pos in (AgentPosition.STRONG_BUY, AgentPosition.STRONG_REDUCE)
        )

        return DebateOutcome(
            event_trigger=event_trigger,
            user_id=user_id,
            arguments=arguments,
            verdict=verdict,
            winning_position=winning_pos,
            final_recommendation=recommendation,
            final_confidence=final_confidence,
            dissenting_agents=dissenters,
            requires_user_approval=needs_approval,
            requires_governance_check=True,
        )
