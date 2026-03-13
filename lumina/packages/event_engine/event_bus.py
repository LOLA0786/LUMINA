"""
LUMINA Event Bus
Routes financial events to the correct agents automatically.

salary_credited  → tax_agent, retirement_agent, risk_agent
market_crash     → portfolio_agent, risk_agent, retirement_agent
loan_closed      → portfolio_agent, retirement_agent
health_emergency → risk_agent

This is what makes LUMINA reactive, not just responsive.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Callable

from lumina.packages.event_engine.financial_events import EventType, FinancialEvent

logger = logging.getLogger("lumina.event_bus")

Handler = Callable[[FinancialEvent], None]

DEFAULT_ROUTING: dict[EventType, list[str]] = {
    EventType.SALARY_CREDITED:   ["tax_agent", "retirement_agent", "risk_agent"],
    EventType.BONUS_RECEIVED:    ["tax_agent", "portfolio_agent"],
    EventType.MARKET_CRASH:      ["portfolio_agent", "risk_agent", "retirement_agent"],
    EventType.RATE_CHANGE:       ["house_purchase_agent", "risk_agent"],
    EventType.RATE_HIKE_ON_LOAN: ["house_purchase_agent", "retirement_agent"],
    EventType.TAX_LAW_CHANGE:    ["tax_agent"],
    EventType.GOAL_AT_RISK:      ["retirement_agent", "portfolio_agent"],
    EventType.LOAN_DISBURSED:    ["risk_agent", "tax_agent"],
    EventType.LOAN_CLOSED:       ["portfolio_agent", "retirement_agent"],
    EventType.HEALTH_EMERGENCY:  ["risk_agent"],
    EventType.JOB_CHANGE:        ["tax_agent", "retirement_agent", "risk_agent"],
    EventType.CHILD_BORN:        ["retirement_agent", "risk_agent", "tax_agent"],
    EventType.SIP_MISSED:        ["retirement_agent"],
    EventType.INHERITANCE_RECEIVED: ["portfolio_agent", "tax_agent", "risk_agent"],
}


class EventBus:

    def __init__(self):
        self._handlers: dict[EventType, list[Handler]] = defaultdict(list)
        self._event_log: list[FinancialEvent] = []

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed %s to %s", handler.__name__, event_type)

    def publish(self, event: FinancialEvent) -> int:
        """Fire an event. Returns number of handlers invoked."""
        self._event_log.append(event)
        handlers = self._handlers.get(event.event_type, [])
        logger.info(
            "[EventBus] %s fired | user=%s severity=%s handlers=%d",
            event.event_type, event.user_id, event.severity, len(handlers),
        )
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("[EventBus] Handler %s failed: %s", handler.__name__, exc)
        event.processed = True
        return len(handlers)

    def event_history(self, user_id: str) -> list[FinancialEvent]:
        return [e for e in self._event_log if e.user_id == user_id]

    def unprocessed(self) -> list[FinancialEvent]:
        return [e for e in self._event_log if not e.processed]

    def routing_summary(self, event_type: EventType) -> list[str]:
        """Which agents handle this event type?"""
        return DEFAULT_ROUTING.get(event_type, [])
