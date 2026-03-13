"""
LUMINA Health Check
Returns system status — used by load balancers,
Cloud Run, and the /health API endpoint.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentHealth:
    name: str
    status: str          # ok | degraded | down
    latency_ms: float = 0.0
    detail: str       = ""


@dataclass
class SystemHealth:
    status: str                        # ok | degraded | down
    version: str                       = "1.0.0"
    environment: str                   = "development"
    uptime_seconds: float              = 0.0
    components: list[ComponentHealth]  = field(default_factory=list)
    checked_at: str                    = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status":       self.status,
            "version":      self.version,
            "environment":  self.environment,
            "uptime_s":     round(self.uptime_seconds, 1),
            "checked_at":   self.checked_at,
            "components":   [
                {
                    "name":       c.name,
                    "status":     c.status,
                    "latency_ms": round(c.latency_ms, 2),
                    "detail":     c.detail,
                }
                for c in self.components
            ],
        }


_start_time = time.time()


def check_health(os_instance=None) -> SystemHealth:
    components: list[ComponentHealth] = []

    # Config
    try:
        from lumina.config.settings import settings
        components.append(ComponentHealth(
            name="config", status="ok",
            detail=f"env={settings.environment}",
        ))
    except Exception as e:
        components.append(ComponentHealth(
            name="config", status="down", detail=str(e)
        ))

    # Audit ledger
    if os_instance:
        try:
            t = time.perf_counter()
            summary = os_instance.audit_ledger.summary()
            lat = (time.perf_counter() - t) * 1000
            valid = summary.get("chain_valid", False)
            components.append(ComponentHealth(
                name       = "audit_ledger",
                status     = "ok" if valid else "degraded",
                latency_ms = lat,
                detail     = (
                    f"entries={summary['total_entries']} "
                    f"chain={'valid' if valid else 'INVALID'}"
                ),
            ))
        except Exception as e:
            components.append(ComponentHealth(
                name="audit_ledger", status="down", detail=str(e)
            ))

    # Event bus
    if os_instance:
        try:
            components.append(ComponentHealth(
                name="event_bus", status="ok",
                detail=f"sessions={len(os_instance._sessions)}",
            ))
        except Exception as e:
            components.append(ComponentHealth(
                name="event_bus", status="down", detail=str(e)
            ))

    overall = (
        "down"     if any(c.status == "down"     for c in components) else
        "degraded" if any(c.status == "degraded" for c in components) else
        "ok"
    )

    from lumina.config.settings import settings
    return SystemHealth(
        status      = overall,
        version     = settings.app_version,
        environment = settings.environment,
        uptime_seconds = time.time() - _start_time,
        components  = components,
        checked_at  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
