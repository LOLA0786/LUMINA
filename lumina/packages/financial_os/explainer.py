"""
LUMINA Explainability Layer
════════════════════════════
Every recommendation rendered in human-readable format.
Trust is the biggest barrier in finance. This solves it.

Output format (for advisor dashboard and client app):
  ┌─────────────────────────────────────────┐
  │ RECOMMENDATION                          │
  │ Increase SIP to ₹30,000/month          │
  │                                         │
  │ WHY                                     │
  │ Retirement gap detected. At current    │
  │ ₹15,000/mo SIP, projected corpus is    │
  │ ₹1.8Cr short of target by age 60.     │
  │                                         │
  │ ASSUMPTIONS                             │
  │ • Return: 10% p.a.                     │
  │ • Inflation: 6% p.a.                   │
  │ • Horizon: 26 years                    │
  │                                         │
  │ CONFIDENCE: 0.87 ████████░░            │
  │ POLICY: ✓ ALLOWED                      │
  │ AUDIT:  abc123def456 (Merkle-logged)   │
  └─────────────────────────────────────────┘
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Explanation:
    recommendation: str
    why: str
    assumptions: list[str]
    confidence: float
    policy_result: str
    audit_hash: str
    dissenting_agents: list[str] = field(default_factory=list)

    def render(self) -> str:
        bar_filled = int(self.confidence * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        policy_icon = "✓" if self.policy_result == "allowed" else "✗"

        lines = [
            "┌" + "─" * 43 + "┐",
            f"│ {'RECOMMENDATION':41} │",
            f"│ {self.recommendation[:41]:41} │",
            "│" + " " * 43 + "│",
            f"│ {'WHY':41} │",
        ]
        for chunk in [self.why[i:i+41] for i in range(0, len(self.why), 41)]:
            lines.append(f"│ {chunk:41} │")
        lines += [
            "│" + " " * 43 + "│",
            f"│ {'ASSUMPTIONS':41} │",
        ]
        for a in self.assumptions:
            lines.append(f"│ • {a[:39]:39} │")
        lines += [
            "│" + " " * 43 + "│",
            f"│ CONFIDENCE: {self.confidence:.2f} {bar}     │",
            f"│ POLICY: {policy_icon} {self.policy_result.upper():33} │",
            f"│ AUDIT:  {self.audit_hash[:12]}... (Merkle-logged)  │",
        ]
        if self.dissenting_agents:
            lines.append(f"│ NOTE: {', '.join(self.dissenting_agents)} dissented    │")
        lines.append("└" + "─" * 43 + "┘")
        return "\n".join(lines)
