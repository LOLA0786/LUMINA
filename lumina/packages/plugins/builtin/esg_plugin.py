"""
LUMINA Built-in Plugin: ESG Scorer
════════════════════════════════════
Scores portfolio for ESG alignment.
Fires on portfolio_check and rebalance events.

Third-party example: any ESG data provider
could register a plugin like this.
"""
from __future__ import annotations
from lumina.packages.plugins.plugin_base import AgentPlugin, PluginResult


# Simplified ESG scores by holding name keyword
ESG_SCORES = {
    "nifty":    0.72,
    "sensex":   0.70,
    "hdfc":     0.78,
    "infosys":  0.85,
    "tcs":      0.83,
    "coal":     0.12,
    "tobacco":  0.08,
    "defence":  0.45,
    "pharma":   0.68,
    "bank":     0.74,
    "energy":   0.50,
    "green":    0.92,
    "solar":    0.95,
}

_DEFAULT_ESG = 0.65


class ESGPlugin(AgentPlugin):
    name        = "esg_agent"
    version     = "1.0.0"
    author      = "LUMINA Core"
    description = "Scores portfolio ESG alignment"
    priority    = 5                      # informational — lowest priority
    event_types = []                     # handles all events

    def analyse(self, snap, event, context) -> PluginResult:
        holdings  = snap.demat_holdings
        if not holdings:
            return PluginResult(
                position   = "HOLD",
                confidence = 0.60,
                reasoning  = "No holdings to score",
            )

        scores = []
        for h in holdings:
            name_lower = h.fund_name.lower()
            score      = _DEFAULT_ESG
            for keyword, s in ESG_SCORES.items():
                if keyword in name_lower:
                    score = s
                    break
            scores.append((h.current_value_inr, score))

        total_val   = sum(v for v, _ in scores) or 1
        weighted    = sum(v * s for v, s in scores) / total_val

        if weighted >= 0.75:
            return PluginResult(
                position   = "HOLD",
                confidence = 0.80,
                reasoning  = (
                    f"Portfolio ESG score {weighted:.2f}/1.0 — "
                    "well aligned"
                ),
                metadata   = {"esg_score": weighted},
            )
        elif weighted >= 0.50:
            return PluginResult(
                position   = "ALERT_ONLY",
                confidence = 0.75,
                reasoning  = (
                    f"Portfolio ESG score {weighted:.2f}/1.0 — "
                    "moderate. Consider ESG funds."
                ),
                recommended_action = "Add one ESG index fund",
                metadata   = {"esg_score": weighted},
            )
        else:
            return PluginResult(
                position   = "REDUCE",
                confidence = 0.70,
                reasoning  = (
                    f"Portfolio ESG score {weighted:.2f}/1.0 — "
                    "low. Significant ESG risk."
                ),
                recommended_action = "Replace low-ESG holdings",
                metadata   = {"esg_score": weighted},
            )
