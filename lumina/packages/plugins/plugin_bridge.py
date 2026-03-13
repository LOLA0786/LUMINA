"""
LUMINA Plugin Bridge
═════════════════════
Connects PluginRegistry to the DebateEngine.

When an event fires:
  1. PluginBridge.get_arguments(event, snapshot)
  2. Queries registry for active plugins
  3. Runs each plugin with isolation
  4. Converts PluginResult → AgentArgument
  5. Returns list ready for DebateEngine.arbitrate()

This is the integration point.
DebateEngine does not know about plugins directly.
PluginBridge is the adapter.
"""
from __future__ import annotations
from typing import Any

from lumina.packages.plugins.plugin_base import PluginResult, PluginStatus
from lumina.packages.plugins.registry.plugin_registry import PluginRegistry
from lumina.packages.autonomous_agents.agent_debate import (
    AgentArgument, AgentPosition,
)
from lumina.observability.logging import get_logger

logger = get_logger("lumina.plugin_bridge")

_POSITION_MAP = {
    "STRONG_BUY":    AgentPosition.STRONG_BUY,
    "BUY":           AgentPosition.BUY,
    "HOLD":          AgentPosition.HOLD,
    "REDUCE":        AgentPosition.REDUCE,
    "STRONG_REDUCE": AgentPosition.STRONG_REDUCE,
    "REBALANCE":     AgentPosition.REBALANCE,
    "ALERT_ONLY":    AgentPosition.ALERT_ONLY,
}


class PluginBridge:
    def __init__(self, registry: PluginRegistry):
        self._registry = registry

    def get_arguments(
        self,
        snapshot:   Any,
        event:      Any,
        context:    dict[str, Any],
    ) -> list[AgentArgument]:
        """
        Run all active plugins for this event.
        Returns AgentArguments ready for DebateEngine.
        """
        event_type = (
            event.event_type.value
            if event and hasattr(event, "event_type")
            else "unknown"
        )
        plugins = self._registry.for_event(event_type)
        if not plugins:
            return []

        arguments = []
        for plugin in plugins:
            record = self._registry.run_plugin(
                plugin, snapshot, event, context
            )
            if (
                record.status == PluginStatus.ACTIVE
                and record.result
            ):
                arg = self._to_argument(plugin, record.result)
                arguments.append(arg)
                logger.info(
                    "bridge.converted",
                    plugin   = plugin.name,
                    position = arg.position.value,
                )

        return arguments

    def _to_argument(
        self,
        plugin: Any,
        result: PluginResult,
    ) -> AgentArgument:
        return AgentArgument(
            agent_name         = plugin.name,
            position           = _POSITION_MAP.get(
                result.position, AgentPosition.HOLD
            ),
            reasoning          = result.reasoning,
            confidence         = result.confidence,
            recommended_action = result.recommended_action,
            recommended_amount_inr = result.amount_inr,
            priority           = plugin.priority,
        )
