"""
LUMINA Base Agent
─────────────────
Every agent in the LUMINA reasoning engine inherits from here.
Enforces:
  - Structured input/output via Pydantic
  - Consent-gate: no reasoning without explicit data consent
  - Audit trail on every invocation
  - Graceful degradation when graph data is incomplete
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger("lumina.agent")


class ConsentLevel(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    FULL = "full"


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"        # answered, but with missing data
    BLOCKED = "blocked"        # consent denied
    FAILED = "failed"


class AgentInput(BaseModel):
    user_id: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consent_level: ConsentLevel = ConsentLevel.READ_ONLY
    context: dict[str, Any] = Field(default_factory=dict)
    raw_query: Optional[str] = None


class AgentOutput(BaseModel):
    session_id: str
    agent_name: str
    status: AgentStatus
    result: Optional[dict[str, Any]] = None
    reasoning_trace: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


InputT = TypeVar("InputT", bound=AgentInput)
OutputT = TypeVar("OutputT", bound=AgentOutput)


class LuminaBaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Abstract base for all LUMINA agents.

    Subclass contract:
      - Define `name: str`
      - Implement `_run(input_data) -> OutputT`
      - Optionally override `_validate_consent()`
    """

    name: str = "base_agent"
    version: str = "0.1.0"
    required_consent: ConsentLevel = ConsentLevel.READ_ONLY

    def __call__(self, input_data: InputT) -> OutputT:
        start = time.perf_counter()

        # Consent gate
        if not self._validate_consent(input_data.consent_level):
            logger.warning(
                "[%s] Consent BLOCKED for user=%s session=%s",
                self.name, input_data.user_id, input_data.session_id
            )
            return self._blocked_response(input_data)  # type: ignore[return-value]

        try:
            logger.info("[%s] Starting | user=%s", self.name, input_data.user_id)
            output: OutputT = self._run(input_data)
            output.latency_ms = (time.perf_counter() - start) * 1000
            self._audit(input_data, output)
            return output
        except Exception as exc:
            logger.exception("[%s] Failed: %s", self.name, exc)
            raise

    @abstractmethod
    def _run(self, input_data: InputT) -> OutputT:
        ...

    def _validate_consent(self, given: ConsentLevel) -> bool:
        order = [ConsentLevel.NONE, ConsentLevel.READ_ONLY, ConsentLevel.FULL]
        return order.index(given) >= order.index(self.required_consent)

    def _blocked_response(self, input_data: InputT) -> AgentOutput:
        return AgentOutput(
            session_id=input_data.session_id,
            agent_name=self.name,
            status=AgentStatus.BLOCKED,
            reasoning_trace=["Consent level insufficient for this agent."],
        )

    def _audit(self, inp: InputT, out: OutputT) -> None:
        logger.info(
            "[AUDIT] agent=%s user=%s session=%s status=%s latency=%.1fms confidence=%.2f",
            self.name, inp.user_id, inp.session_id,
            out.status, out.latency_ms, out.confidence,
        )
