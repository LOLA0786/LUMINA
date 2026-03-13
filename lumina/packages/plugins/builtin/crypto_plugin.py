"""
LUMINA Built-in Plugin: Crypto Risk Analyser
══════════════════════════════════════════════
Reference implementation for external developers.
Detects excessive crypto concentration.
"""
from __future__ import annotations
from lumina.packages.plugins.plugin_base import AgentPlugin, PluginResult

MAX_CRYPTO_PCT = 0.10     # 10% max


class CryptoRiskPlugin(AgentPlugin):
    name        = "crypto_risk_agent"
    version     = "1.0.0"
    author      = "LUMINA Core"
    description = "Detects crypto concentration risk"
    priority    = 2
    event_types = ["market_crash", "portfolio_check", "rebalance"]

    def analyse(self, snap, event, context) -> PluginResult:
        total      = snap.total_assets_inr
        crypto_val = sum(
            h.current_value_inr for h in snap.demat_holdings
            if h.holding_type.value in ("crypto",)
        )
        if total == 0:
            return PluginResult(position="HOLD", confidence=0.70)

        crypto_pct = crypto_val / total

        if crypto_pct > MAX_CRYPTO_PCT:
            excess = crypto_val - (total * MAX_CRYPTO_PCT)
            return PluginResult(
                position   = "REDUCE",
                confidence = 0.88,
                reasoning  = (
                    f"Crypto {crypto_pct:.0%} of portfolio — "
                    f"exceeds {MAX_CRYPTO_PCT:.0%} limit"
                ),
                recommended_action = (
                    f"Reduce crypto by ₹{excess/1e5:.1f}L"
                ),
                amount_inr = excess,
            )
        return PluginResult(
            position   = "HOLD",
            confidence = 0.82,
            reasoning  = (
                f"Crypto {crypto_pct:.0%} — within limit"
            ),
        )
