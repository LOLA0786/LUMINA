"""
LUMINA Built-in Plugin: Insurance Gap Analyser
════════════════════════════════════════════════
Detects under-insurance on salary_credited
and goal_at_risk events.

This is also the reference implementation
for third-party plugin authors.
"""
from __future__ import annotations
from lumina.packages.plugins.plugin_base import AgentPlugin, PluginResult


class InsuranceGapPlugin(AgentPlugin):
    name        = "insurance_gap_agent"
    version     = "1.0.0"
    author      = "LUMINA Core"
    description = "Detects life and health insurance gaps"
    priority    = 2
    event_types = [
        "salary_credited", "goal_at_risk",
        "child_born", "job_change",
    ]

    def analyse(self, snap, event, context) -> PluginResult:
        annual_income  = snap.monthly_income_inr * 12
        required_cover = annual_income * 12      # 12x rule
        sum_assured    = sum(
            p.sum_assured_inr for p in snap.insurance_policies
            if p.policy_type == "term"
        )
        gap = max(0, required_cover - sum_assured)

        if gap > 0:
            coverage_pct = sum_assured / required_cover
            return PluginResult(
                position   = "ALERT_ONLY",
                confidence = 0.93,
                reasoning  = (
                    f"Life cover ₹{sum_assured/1e7:.1f}Cr vs "
                    f"required ₹{required_cover/1e7:.1f}Cr — "
                    f"gap ₹{gap/1e7:.1f}Cr ({coverage_pct:.0%} covered)"
                ),
                recommended_action = (
                    f"Buy term cover of ₹{gap/1e7:.1f}Cr"
                ),
                amount_inr = gap,
                metadata   = {
                    "coverage_pct": coverage_pct,
                    "gap_inr":      gap,
                },
            )
        return PluginResult(
            position   = "HOLD",
            confidence = 0.90,
            reasoning  = "Life cover adequate — no action needed",
        )
