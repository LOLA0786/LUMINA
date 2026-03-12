"""LUMINA output formatters — clean human-readable summaries."""

from __future__ import annotations


def inr(amount: float) -> str:
    """Format as Indian Rupee with lakh/crore notation."""
    if amount >= 1e7:
        return f"₹{amount/1e7:.2f} Cr"
    elif amount >= 1e5:
        return f"₹{amount/1e5:.2f} L"
    else:
        return f"₹{amount:,.0f}"


def pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def agent_report(output: dict) -> str:
    """Render an agent output dict as a clean text report."""
    lines = [
        f"Agent    : {output.get('agent_name', 'unknown')}",
        f"Status   : {output.get('status', '?')}",
        f"Confidence: {output.get('confidence', 0):.0%}",
        f"Latency  : {output.get('latency_ms', 0):.0f}ms",
        "",
    ]
    if output.get("reasoning_trace"):
        lines.append("Reasoning Trace:")
        for step in output["reasoning_trace"]:
            lines.append(f"  → {step}")
    if output.get("warnings"):
        lines.append("\nWarnings:")
        for w in output["warnings"]:
            lines.append(f"  ⚠ {w}")
    return "\n".join(lines)
