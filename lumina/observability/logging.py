"""
LUMINA Structured Logging
Every agent call, event, governance decision gets:
  - correlation_id  : trace a request end-to-end
  - user_id         : filter logs per client
  - agent_name      : filter logs per agent
  - latency_ms      : spot slow agents instantly
  - JSON format     : ingest into Cloud Logging / Datadog

Usage:
    from lumina.observability.logging import get_logger, bind_context
    logger = get_logger(__name__)
    logger.info("agent.started", agent="risk_agent", user="u001")
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

# ── Context vars (per-request, async-safe) ───────────────────────────
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_user_id: ContextVar[str]        = ContextVar("user_id",        default="")
_agent_name: ContextVar[str]     = ContextVar("agent_name",     default="")


def new_correlation_id() -> str:
    return str(uuid.uuid4())[:8]


def bind_context(
    correlation_id: Optional[str] = None,
    user_id: str = "",
    agent_name: str = "",
) -> str:
    cid = correlation_id or new_correlation_id()
    _correlation_id.set(cid)
    _user_id.set(user_id)
    _agent_name.set(agent_name)
    return cid


def get_context() -> dict[str, str]:
    return {
        "correlation_id": _correlation_id.get(),
        "user_id":        _user_id.get(),
        "agent_name":     _agent_name.get(),
    }


# ── JSON formatter ───────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """
    Emits one JSON object per log line.
    Compatible with Google Cloud Logging, Datadog, ELK.
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_context()
        payload: dict[str, Any] = {
            "timestamp":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":          record.levelname,
            "logger":         record.name,
            "message":        record.getMessage(),
            "correlation_id": ctx["correlation_id"],
            "user_id":        ctx["user_id"],
            "agent_name":     ctx["agent_name"],
        }
        # Merge any extra kwargs passed to the logger
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class LuminaLogger(logging.LoggerAdapter):
    """
    Logger with structured field support.

    Usage:
        logger = get_logger("lumina.agents.risk")
        logger.info("agent.complete",
                    latency_ms=42.3, confidence=0.87, status="success")
    """

    def process(
        self, msg: str, kwargs: dict
    ) -> tuple[str, dict]:
        extra = kwargs.pop("extra", {})
        # Collect all extra keyword args as structured fields
        extra_fields = {
            k: v for k, v in kwargs.items()
            if k not in ("exc_info", "stack_info", "stacklevel")
        }
        for k in extra_fields:
            kwargs.pop(k)
        extra["extra_fields"] = {**get_context(), **extra_fields}
        kwargs["extra"] = extra
        return msg, kwargs


# ── Setup ────────────────────────────────────────────────────────────
_configured = False


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
        ))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Silence noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> LuminaLogger:
    configure_logging()
    return LuminaLogger(logging.getLogger(name), extra={})


# ── Decorators ───────────────────────────────────────────────────────
def log_agent_call(agent_name: str):
    """
    Decorator — wraps any agent _run() method with:
      - automatic correlation ID
      - latency measurement
      - success/failure structured log
    """
    def decorator(fn: Callable) -> Callable:
        logger = get_logger(f"lumina.agent.{agent_name}")

        @wraps(fn)
        def wrapper(self, input_data, *args, **kwargs):
            cid = bind_context(
                user_id    = getattr(input_data, "user_id", ""),
                agent_name = agent_name,
            )
            start = time.perf_counter()
            logger.info(
                "agent.started",
                session_id = getattr(input_data, "session_id", ""),
            )
            try:
                result = fn(self, input_data, *args, **kwargs)
                latency = (time.perf_counter() - start) * 1000
                logger.info(
                    "agent.completed",
                    latency_ms = round(latency, 2),
                    status     = getattr(result, "status", "unknown"),
                    confidence = getattr(result, "confidence", 0),
                )
                return result
            except Exception as exc:
                latency = (time.perf_counter() - start) * 1000
                logger.error(
                    "agent.failed",
                    latency_ms = round(latency, 2),
                    error      = str(exc),
                    exc_info   = True,
                )
                raise
        return wrapper
    return decorator


def log_event(fn: Callable) -> Callable:
    """
    Decorator — wraps EventBus.publish() with structured logging.
    """
    logger = get_logger("lumina.event_bus")

    @wraps(fn)
    def wrapper(self, event, *args, **kwargs):
        cid = bind_context(user_id=getattr(event, "user_id", ""))
        logger.info(
            "event.published",
            event_type = getattr(event, "event_type", "unknown"),
            severity   = getattr(event, "severity", "unknown"),
            source     = getattr(event, "source", "unknown"),
        )
        result = fn(self, event, *args, **kwargs)
        logger.info("event.processed", handlers_fired=result)
        return result
    return wrapper


def log_governance(fn: Callable) -> Callable:
    """
    Decorator — wraps PolicyEngine.evaluate() with structured logging.
    """
    logger = get_logger("lumina.governance")

    @wraps(fn)
    def wrapper(self, request, profile, *args, **kwargs):
        bind_context(user_id=getattr(request, "user_id", ""))
        logger.info(
            "policy.evaluating",
            action     = getattr(request, "action_type", "unknown"),
            confidence = getattr(request, "confidence", 0),
        )
        decision = fn(self, request, profile, *args, **kwargs)
        logger.info(
            "policy.decided",
            result     = getattr(decision, "result", "unknown"),
            violations = len(getattr(decision, "violations", [])),
            flags      = len(getattr(decision, "flags", [])),
            receipt    = getattr(decision, "receipt_hash", "")[:12],
        )
        return decision
    return wrapper
