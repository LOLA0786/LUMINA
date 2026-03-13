"""
LUMINA Plugin System — Base
════════════════════════════
Third-party agents plug into the debate engine.
External developers build new agents and register them.

Plugin contract:
  1. Inherit from AgentPlugin
  2. Implement analyse() → PluginResult
  3. Register with PluginRegistry
  4. DebateEngine picks it up automatically

That is the entire API surface.
One class. One method. Full integration.

Example third-party plugin:

    class CryptoRiskPlugin(AgentPlugin):
        name        = "crypto_risk_agent"
        version     = "1.0.0"
        author      = "CryptoAdvisors Ltd"
        description = "Analyses crypto exposure risk"
        priority    = 3

        def analyse(
            self, twin_snapshot, event, context
        ) -> PluginResult:
            crypto_val = sum(
                h.current_value_inr
                for h in twin_snapshot.demat_holdings
                if h.holding_type.value == "crypto"
            )
            if crypto_val > twin_snapshot.total_assets_inr * 0.10:
                return PluginResult(
                    position   = "REDUCE",
                    reasoning  = "Crypto > 10% of portfolio",
                    confidence = 0.88,
                    amount_inr = crypto_val * 0.50,
                )
            return PluginResult(position="HOLD", confidence=0.70)

Plugin isolation:
  - Plugins run in try/except — one bad plugin
    cannot crash the debate engine
  - Timeout enforced per plugin (default 2s)
  - Plugin results are validated before use
  - Malformed results are logged and skipped
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PluginStatus(str, Enum):
    ACTIVE    = "active"
    DISABLED  = "disabled"
    ERROR     = "error"
    TIMEOUT   = "timeout"


@dataclass
class PluginResult:
    """
    What a plugin returns from analyse().
    Maps directly to AgentArgument in debate engine.
    """
    position:           str              # STRONG_BUY/BUY/HOLD/REDUCE/STRONG_REDUCE/ALERT_ONLY
    confidence:         float            = 0.70
    reasoning:          str              = ""
    recommended_action: str              = ""
    amount_inr:         Optional[float]  = None
    metadata:           dict[str, Any]   = field(default_factory=dict)

    def is_valid(self) -> bool:
        valid_positions = {
            "STRONG_BUY","BUY","HOLD",
            "REDUCE","STRONG_REDUCE",
            "REBALANCE","ALERT_ONLY",
        }
        return (
            self.position in valid_positions
            and 0.0 <= self.confidence <= 1.0
        )


@dataclass
class PluginRunRecord:
    """Execution record for one plugin run."""
    plugin_name:  str
    user_id:      str
    event_type:   str
    status:       PluginStatus
    latency_ms:   float
    result:       Optional[PluginResult] = None
    error:        str                    = ""
    timestamp:    float = field(default_factory=time.time)


class AgentPlugin(ABC):
    """
    Base class for all LUMINA plugins.

    Class attributes (set by plugin author):
      name        — unique identifier (snake_case)
      version     — semver string
      author      — author or org name
      description — one-line description
      priority    — debate weight 1-5 (1=highest)
      event_types — list of events this plugin handles
                    empty list = handles all events
    """
    name:        str       = "unnamed_plugin"
    version:     str       = "0.0.1"
    author:      str       = "unknown"
    description: str       = ""
    priority:    int       = 3
    event_types: list[str] = []        # [] = all events
    timeout_sec: float     = 2.0

    def handles(self, event_type: str) -> bool:
        """Does this plugin handle this event type?"""
        return (
            not self.event_types
            or event_type in self.event_types
        )

    @abstractmethod
    def analyse(
        self,
        twin_snapshot: Any,
        event:         Any,
        context:       dict[str, Any],
    ) -> PluginResult:
        """
        Core plugin logic.
        Receives the current twin snapshot + triggering event.
        Returns a PluginResult.
        Must complete within timeout_sec.
        """
        ...

    def on_load(self) -> None:
        """Called once when plugin is registered. Optional."""

    def on_unload(self) -> None:
        """Called when plugin is removed. Optional."""

    def health_check(self) -> bool:
        """Return True if plugin is operational. Optional."""
        return True

    def metadata(self) -> dict[str, Any]:
        return {
            "name":        self.name,
            "version":     self.version,
            "author":      self.author,
            "description": self.description,
            "priority":    self.priority,
            "event_types": self.event_types,
            "timeout_sec": self.timeout_sec,
        }
