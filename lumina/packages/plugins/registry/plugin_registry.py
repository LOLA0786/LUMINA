"""
LUMINA Plugin Registry
═══════════════════════
Central store for all registered plugins.
DebateEngine queries this on every event.

Registration:
    registry = PluginRegistry()
    registry.register(CryptoRiskPlugin())
    registry.register(ESGPlugin())

Discovery:
    plugins = registry.for_event("market_crash")
    # returns all active plugins that handle market_crash

Isolation:
    registry.run_plugin(plugin, snapshot, event, ctx)
    # runs in try/except + timeout guard
    # bad plugins never crash the debate engine
"""
from __future__ import annotations

import time
import threading
from typing import Any, Optional

from lumina.packages.plugins.plugin_base import (
    AgentPlugin, PluginResult, PluginRunRecord, PluginStatus,
)
from lumina.observability.logging import get_logger

logger = get_logger("lumina.plugin_registry")


class PluginRegistry:
    """
    Thread-safe plugin registry.
    Supports register / unregister / enable / disable.
    Runs plugins with timeout isolation.
    """

    def __init__(self):
        self._plugins:  dict[str, AgentPlugin] = {}
        self._status:   dict[str, PluginStatus] = {}
        self._run_log:  list[PluginRunRecord]   = []
        self._lock      = threading.Lock()

    # ── Registration ──────────────────────────────────────────────

    def register(self, plugin: AgentPlugin) -> bool:
        """
        Register a plugin.
        Calls plugin.on_load() and health_check().
        Returns True if registration succeeded.
        """
        with self._lock:
            if plugin.name in self._plugins:
                logger.warning(
                    "plugin.already_registered",
                    name = plugin.name,
                )
                return False

            try:
                plugin.on_load()
                healthy = plugin.health_check()
            except Exception as e:
                logger.error(
                    "plugin.load_failed",
                    name  = plugin.name,
                    error = str(e),
                )
                return False

            self._plugins[plugin.name] = plugin
            self._status[plugin.name]  = (
                PluginStatus.ACTIVE
                if healthy
                else PluginStatus.ERROR
            )

            logger.info(
                "plugin.registered",
                name    = plugin.name,
                version = plugin.version,
                author  = plugin.author,
                status  = self._status[plugin.name].value,
            )
            return True

    def unregister(self, name: str) -> bool:
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                return False
            try:
                plugin.on_unload()
            except Exception:
                pass
            del self._plugins[name]
            del self._status[name]
            logger.info("plugin.unregistered", name=name)
            return True

    def enable(self, name: str) -> None:
        with self._lock:
            if name in self._status:
                self._status[name] = PluginStatus.ACTIVE
                logger.info("plugin.enabled", name=name)

    def disable(self, name: str) -> None:
        with self._lock:
            if name in self._status:
                self._status[name] = PluginStatus.DISABLED
                logger.info("plugin.disabled", name=name)

    # ── Discovery ─────────────────────────────────────────────────

    def for_event(self, event_type: str) -> list[AgentPlugin]:
        """
        Return all active plugins that handle this event type.
        Sorted by priority (1 = highest priority first).
        """
        with self._lock:
            return sorted(
                [
                    p for name, p in self._plugins.items()
                    if self._status[name] == PluginStatus.ACTIVE
                    and p.handles(event_type)
                ],
                key=lambda p: p.priority,
            )

    def all_plugins(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    **p.metadata(),
                    "status": self._status[n].value,
                }
                for n, p in self._plugins.items()
            ]

    def get(self, name: str) -> Optional[AgentPlugin]:
        return self._plugins.get(name)

    # ── Execution ─────────────────────────────────────────────────

    def run_plugin(
        self,
        plugin:   AgentPlugin,
        snapshot: Any,
        event:    Any,
        context:  dict[str, Any],
    ) -> PluginRunRecord:
        """
        Run a plugin with timeout isolation.

        If plugin raises or times out:
          - PluginRunRecord.status = ERROR or TIMEOUT
          - Plugin is NOT unregistered (transient failure)
          - DebateEngine continues with other plugins
        """
        start      = time.perf_counter()
        result_box: list[Optional[PluginResult]] = [None]
        error_box:  list[str]                    = [""]

        def target():
            try:
                result_box[0] = plugin.analyse(
                    snapshot, event, context
                )
            except Exception as e:
                error_box[0] = str(e)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=plugin.timeout_sec)

        latency = (time.perf_counter() - start) * 1000

        if thread.is_alive():
            # Timeout
            with self._lock:
                self._status[plugin.name] = PluginStatus.TIMEOUT
            record = PluginRunRecord(
                plugin_name = plugin.name,
                user_id     = getattr(snapshot, "user_id", ""),
                event_type  = getattr(
                    event, "event_type", ""
                ).value if event else "",
                status      = PluginStatus.TIMEOUT,
                latency_ms  = latency,
                error       = f"Timeout after {plugin.timeout_sec}s",
            )
            logger.warning(
                "plugin.timeout",
                name       = plugin.name,
                latency_ms = round(latency, 2),
            )
        elif error_box[0]:
            with self._lock:
                self._status[plugin.name] = PluginStatus.ERROR
            record = PluginRunRecord(
                plugin_name = plugin.name,
                user_id     = getattr(snapshot, "user_id", ""),
                event_type  = "",
                status      = PluginStatus.ERROR,
                latency_ms  = latency,
                error       = error_box[0],
            )
            logger.error(
                "plugin.error",
                name  = plugin.name,
                error = error_box[0],
            )
        else:
            result = result_box[0]
            if result and not result.is_valid():
                record = PluginRunRecord(
                    plugin_name = plugin.name,
                    user_id     = getattr(snapshot, "user_id", ""),
                    event_type  = "",
                    status      = PluginStatus.ERROR,
                    latency_ms  = latency,
                    error       = f"Invalid result: {result.position}",
                )
            else:
                record = PluginRunRecord(
                    plugin_name = plugin.name,
                    user_id     = getattr(snapshot, "user_id", ""),
                    event_type  = "",
                    status      = PluginStatus.ACTIVE,
                    latency_ms  = latency,
                    result      = result,
                )
                logger.info(
                    "plugin.ran",
                    name       = plugin.name,
                    position   = result.position if result else "none",
                    confidence = result.confidence if result else 0,
                    latency_ms = round(latency, 2),
                )

        self._run_log.append(record)
        return record

    # ── Observability ─────────────────────────────────────────────

    def run_summary(self) -> dict[str, Any]:
        total   = len(self._run_log)
        success = sum(
            1 for r in self._run_log
            if r.status == PluginStatus.ACTIVE
        )
        errors  = sum(
            1 for r in self._run_log
            if r.status == PluginStatus.ERROR
        )
        timeouts= sum(
            1 for r in self._run_log
            if r.status == PluginStatus.TIMEOUT
        )
        avg_lat = (
            sum(r.latency_ms for r in self._run_log) / total
            if total else 0
        )
        return {
            "total_runs":   total,
            "success":      success,
            "errors":       errors,
            "timeouts":     timeouts,
            "avg_latency_ms": round(avg_lat, 2),
            "registered":   len(self._plugins),
            "active":       sum(
                1 for s in self._status.values()
                if s == PluginStatus.ACTIVE
            ),
        }

    def render(self) -> str:
        lines = [
            "┌" + "─" * 54 + "┐",
            "│  LUMINA PLUGIN REGISTRY" + " " * 30 + "│",
            "├" + "─" * 54 + "┤",
        ]
        for name, plugin in self._plugins.items():
            status = self._status[name].value
            icon   = "✓" if status == "active" else "✗"
            lines.append(
                f"│  {icon} {plugin.name:<28} "
                f"v{plugin.version:<8} "
                f"{status:<8}  │"
            )
            lines.append(
                f"│    {plugin.description[:50]:<50}  │"
            )
        lines.append("├" + "─" * 54 + "┤")
        s = self.run_summary()
        lines.append(
            f"│  Runs: {s['total_runs']} | "
            f"OK: {s['success']} | "
            f"Err: {s['errors']} | "
            f"Avg: {s['avg_latency_ms']}ms"
            + " " * 8 + "│"
        )
        lines.append("└" + "─" * 54 + "┘")
        return "\n".join(lines)
