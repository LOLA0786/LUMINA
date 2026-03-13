"""
LUMINA Connector Hub
═════════════════════
Orchestrates all connectors for a user.

Single call:
  hub.sync(user_id, twin, event_bus)

Runs all registered connectors in sequence.
Returns a ConnectorHubResult with all outcomes.

Production use:
  - Run on schedule (daily at 6am)
  - Run on user login
  - Run on manual refresh
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from lumina.packages.connectors.connector_base import (
    BaseConnector, ConnectorResult,
)
from lumina.observability.logging import get_logger

logger = get_logger("lumina.connector_hub")


@dataclass
class HubSyncResult:
    user_id:         str
    connectors_run:  int
    connectors_ok:   int
    total_records:   int
    total_events:    int
    twin_updated:    bool
    results:         list[ConnectorResult]
    latency_ms:      float
    synced_at:       float = field(default_factory=time.time)

    def render(self) -> str:
        lines = [
            "┌" + "─" * 54 + "┐",
            f"│  CONNECTOR HUB SYNC — {self.user_id:<30}│",
            "├" + "─" * 54 + "┤",
            f"│  Connectors run  : {self.connectors_run:<34}│",
            f"│  Successful      : {self.connectors_ok:<34}│",
            f"│  Records fetched : {self.total_records:<34}│",
            f"│  Events fired    : {self.total_events:<34}│",
            f"│  Twin updated    : "
            f"{'YES' if self.twin_updated else 'NO':<34}│",
            f"│  Total latency   : {self.latency_ms:.0f}ms"
            f"{'':29}│",
            "├" + "─" * 54 + "┤",
        ]
        for r in self.results:
            icon = "✓" if r.success else "✗"
            lines.append(
                f"│  {icon} {r.connector_name:<24} "
                f"{r.records_fetched:>4} records  "
                f"{r.latency_ms:>5.0f}ms  │"
            )
            if not r.success:
                lines.append(
                    f"│    ERROR: {r.error[:44]:44}  │"
                )
        lines.append("└" + "─" * 54 + "┘")
        return "\n".join(lines)


class ConnectorHub:
    """
    Runs all registered connectors for a user.
    Returns unified HubSyncResult.
    """

    def __init__(self):
        self._connectors: list[BaseConnector] = []

    def register(self, connector: BaseConnector) -> None:
        self._connectors.append(connector)
        logger.info(
            "hub.registered",
            connector = connector.name,
            sandbox   = connector.sandbox,
        )

    def sync(
        self,
        user_id:   str,
        twin:      Any  = None,
        event_bus: Any  = None,
    ) -> HubSyncResult:
        start    = time.perf_counter()
        results  = []
        ok       = 0
        records  = 0
        events   = 0
        updated  = False

        for connector in self._connectors:
            result = connector.fetch(
                user_id   = user_id,
                twin      = twin,
                event_bus = event_bus,
            )
            results.append(result)
            if result.success:
                ok      += 1
                records += result.records_fetched
                events  += result.events_fired
                if result.twin_updated:
                    updated = True

        latency = (time.perf_counter() - start) * 1000
        hub_result = HubSyncResult(
            user_id        = user_id,
            connectors_run = len(self._connectors),
            connectors_ok  = ok,
            total_records  = records,
            total_events   = events,
            twin_updated   = updated,
            results        = results,
            latency_ms     = latency,
        )

        logger.info(
            "hub.sync_complete",
            user_id   = user_id,
            ok        = ok,
            records   = records,
            events    = events,
            latency_ms= round(latency, 2),
        )
        return hub_result
