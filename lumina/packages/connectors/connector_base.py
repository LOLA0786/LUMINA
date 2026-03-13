"""
LUMINA Connector Base
══════════════════════
All data connectors inherit from BaseConnector.

A connector:
  1. Fetches data from an external source
     (bank, broker, GST, UPI, credit bureau)
  2. Normalises it into LUMINA's data model
  3. Fires events onto the EventBus
  4. Updates the FinancialTwin

Connector lifecycle:
  connect() → fetch() → normalise() → emit() → disconnect()

Every connector:
  - Retries on transient failures (max 3)
  - Returns ConnectorResult (never raises)
  - Logs structured fields for observability
  - Marks data with source + fetched_at timestamp

In production: connectors call real APIs.
Today: sandbox mode returns realistic mock data.
Sandbox is indistinguishable from production
in terms of data shape and event types fired.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.observability.logging import get_logger

logger = get_logger("lumina.connectors")


class ConnectorStatus(str, Enum):
    CONNECTED    = "connected"
    DISCONNECTED = "disconnected"
    ERROR        = "error"
    SANDBOX      = "sandbox"
    RATE_LIMITED = "rate_limited"


class ConnectorType(str, Enum):
    ACCOUNT_AGGREGATOR = "account_aggregator"
    UPI                = "upi"
    GST                = "gst"
    BROKER             = "broker"
    CREDIT_BUREAU      = "credit_bureau"
    INSURANCE          = "insurance"
    MF_REGISTRY        = "mf_registry"
    EPFO               = "epfo"


@dataclass
class ConnectorResult:
    """
    Every connector fetch returns this.
    Never raises — errors are captured here.
    """
    connector_name: str
    connector_type: ConnectorType
    success:        bool
    records_fetched:int                  = 0
    events_fired:   int                  = 0
    twin_updated:   bool                 = False
    data:           list[dict[str, Any]] = field(default_factory=list)
    error:          str                  = ""
    latency_ms:     float                = 0.0
    fetched_at:     float                = field(default_factory=time.time)
    sandbox:        bool                 = True
    source_ref:     str                  = ""     # external tx/session ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector":      self.connector_name,
            "type":           self.connector_type.value,
            "success":        self.success,
            "records":        self.records_fetched,
            "events_fired":   self.events_fired,
            "twin_updated":   self.twin_updated,
            "error":          self.error,
            "latency_ms":     round(self.latency_ms, 2),
            "fetched_at":     self.fetched_at,
            "sandbox":        self.sandbox,
        }


class BaseConnector(ABC):
    """
    Base for all LUMINA data connectors.

    Subclasses implement:
      _fetch_raw()      — call external API
      _normalise()      — map to LUMINA data model
      _emit_events()    — fire onto EventBus

    BaseConnector handles:
      - Retry logic (max 3 attempts)
      - Timing + structured logging
      - ConnectorResult assembly
      - Sandbox mode toggle
    """
    name:           str           = "base_connector"
    connector_type: ConnectorType = ConnectorType.ACCOUNT_AGGREGATOR
    sandbox:        bool          = True
    max_retries:    int           = 3
    retry_delay_sec:float         = 1.0

    def __init__(self):
        self._status   = ConnectorStatus.SANDBOX if self.sandbox \
                         else ConnectorStatus.DISCONNECTED
        self._session_id = str(uuid.uuid4())[:8]

    def fetch(
        self,
        user_id:    str,
        twin:       Any          = None,
        event_bus:  Any          = None,
        **kwargs,
    ) -> ConnectorResult:
        """
        Main entry point.
        Retries on failure, returns ConnectorResult always.
        """
        start = time.perf_counter()
        logger.info(
            "connector.fetch_start",
            connector = self.name,
            user_id   = user_id,
            sandbox   = self.sandbox,
        )

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                raw    = self._fetch_raw(user_id, **kwargs)
                data   = self._normalise(raw, user_id)
                events = 0
                if event_bus:
                    events = self._emit_events(
                        data, user_id, event_bus
                    )
                updated = False
                if twin:
                    updated = self._update_twin(data, twin)

                latency = (time.perf_counter() - start) * 1000
                result  = ConnectorResult(
                    connector_name = self.name,
                    connector_type = self.connector_type,
                    success        = True,
                    records_fetched= len(data),
                    events_fired   = events,
                    twin_updated   = updated,
                    data           = data,
                    latency_ms     = latency,
                    sandbox        = self.sandbox,
                    source_ref     = self._session_id,
                )
                logger.info(
                    "connector.fetch_ok",
                    connector = self.name,
                    user_id   = user_id,
                    records   = len(data),
                    events    = events,
                    latency_ms= round(latency, 2),
                )
                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "connector.fetch_retry",
                    connector = self.name,
                    attempt   = attempt,
                    error     = last_error,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_sec * attempt)

        latency = (time.perf_counter() - start) * 1000
        logger.error(
            "connector.fetch_failed",
            connector = self.name,
            user_id   = user_id,
            error     = last_error,
        )
        return ConnectorResult(
            connector_name = self.name,
            connector_type = self.connector_type,
            success        = False,
            error          = last_error,
            latency_ms     = latency,
            sandbox        = self.sandbox,
        )

    @abstractmethod
    def _fetch_raw(self, user_id: str, **kwargs) -> list[dict]:
        """Call external API. Return raw records."""

    @abstractmethod
    def _normalise(
        self, raw: list[dict], user_id: str
    ) -> list[dict[str, Any]]:
        """Map raw records to LUMINA data model."""

    def _emit_events(
        self, data: list[dict], user_id: str, event_bus: Any
    ) -> int:
        """Fire events onto EventBus. Override per connector."""
        return 0

    def _update_twin(self, data: list[dict], twin: Any) -> bool:
        """Update FinancialTwin with normalised data. Override."""
        return False

    def status(self) -> ConnectorStatus:
        return self._status
