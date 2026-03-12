"""
LUMINA Session Memory
─────────────────────
Passes context between agents in a multi-hop planner call.
Each agent can read prior agent outputs from the session window.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MemoryEntry:
    agent_name: str
    key: str
    value: Any
    confidence: float = 1.0


class SessionMemory:
    def __init__(self, max_entries: int = 50):
        self._store: deque[MemoryEntry] = deque(maxlen=max_entries)

    def write(self, agent_name: str, key: str, value: Any, confidence: float = 1.0) -> None:
        self._store.append(MemoryEntry(agent_name, key, value, confidence))

    def read(self, key: str) -> Optional[Any]:
        for entry in reversed(self._store):
            if entry.key == key:
                return entry.value
        return None

    def read_all(self) -> list[MemoryEntry]:
        return list(self._store)

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for entry in self._store:
            result[entry.key] = entry.value
        return result
