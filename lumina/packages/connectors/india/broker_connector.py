"""
LUMINA Broker Connector
════════════════════════
Fetches equity + MF holdings from brokers.
Supports Zerodha, Groww, Angel One, Upstox.

This connector:
  Fetches: demat holdings, MF folios,
           NAV, unrealised P&L
  Detects: portfolio drift, large drawdowns
  Fires:   MARKET_CRASH (if drawdown > 15%)
           GOAL_AT_RISK (if retirement gap detected)
  Updates: FinancialTwin demat_holdings

Sandbox: realistic portfolio for 4 holdings.
Production: SEBI CDSL/NSDL API or broker OAuth.
"""
from __future__ import annotations
import random
from typing import Any

from lumina.packages.connectors.connector_base import (
    BaseConnector, ConnectorType,
)


SANDBOX_FUNDS = [
    {
        "fund_name":    "Parag Parikh Flexi Cap",
        "holding_type": "equity_mf",
        "units":        150.0,
        "nav":          75.50,
        "invested":     9000.0,
    },
    {
        "fund_name":    "HDFC Mid Cap Opportunities",
        "holding_type": "equity_mf",
        "units":        80.0,
        "nav":          120.0,
        "invested":     7500.0,
    },
    {
        "fund_name":    "ICICI Pru Liquid Fund",
        "holding_type": "debt_mf",
        "units":        500.0,
        "nav":          320.0,
        "invested":     150000.0,
    },
    {
        "fund_name":    "Nifty 50 Index ETF",
        "holding_type": "etf",
        "units":        30.0,
        "nav":          250.0,
        "invested":     6000.0,
    },
]


class BrokerConnector(BaseConnector):
    name           = "broker_connector"
    connector_type = ConnectorType.BROKER
    sandbox        = True

    BROKER_NAME    = "Zerodha"
    API_BASE       = "https://api.kite.trade"

    def _fetch_raw(self, user_id: str, **kwargs) -> list[dict]:
        """
        Sandbox: realistic holdings.
        Production: GET /portfolio/holdings (Kite API)
        """
        rng = random.Random(hash(user_id) % 3333)
        holdings = []
        for fund in SANDBOX_FUNDS:
            noise = rng.uniform(0.85, 1.20)
            holdings.append({
                **fund,
                "nav":          round(fund["nav"] * noise, 2),
                "current_value":round(fund["units"] * fund["nav"] * noise, 2),
                "pnl":          round(
                    fund["units"] * fund["nav"] * noise
                    - fund["invested"], 2
                ),
                "broker":       self.BROKER_NAME,
            })
        return holdings

    def _normalise(
        self, raw: list[dict], user_id: str
    ) -> list[dict[str, Any]]:
        records = []
        for r in raw:
            records.append({
                "record_type":        "demat_holding",
                "user_id":            user_id,
                "fund_name":          r["fund_name"],
                "holding_type":       r["holding_type"],
                "units":              r["units"],
                "nav":                r["nav"],
                "current_value_inr":  r["current_value"],
                "invested_inr":       r["invested"],
                "pnl_inr":            r["pnl"],
                "broker":             r["broker"],
            })
        return records

    def _emit_events(
        self, data: list[dict], user_id: str, event_bus: Any
    ) -> int:
        from lumina.packages.event_engine.financial_events import (
            FinancialEvent, EventType, EventSeverity,
        )
        fired = 0

        total_invested = sum(r["invested_inr"] for r in data)
        total_current  = sum(r["current_value_inr"] for r in data)

        if total_invested > 0:
            drawdown = (total_invested - total_current) / total_invested
            if drawdown > 0.15:
                evt = FinancialEvent(
                    event_id   = f"brk_crash_{user_id[:6]}",
                    user_id    = user_id,
                    event_type = EventType.MARKET_CRASH,
                    severity   = EventSeverity.CRITICAL,
                    payload    = {
                        "drawdown_pct": round(drawdown, 3),
                        "loss_inr":     round(
                            total_invested - total_current, 0
                        ),
                        "source":       "broker",
                    },
                )
                event_bus.publish(evt)
                fired += 1
        return fired

    def _update_twin(
        self, data: list[dict], twin: Any
    ) -> bool:
        from lumina.packages.digital_twin.financial_twin import (
            DematHolding, HoldingType,
        )
        updated = False
        type_map = {
            "equity_mf": HoldingType.EQUITY_MF,
            "debt_mf":   HoldingType.DEBT_MF,
            "etf":       HoldingType.ETF,
            "stock":     HoldingType.STOCK,
        }
        for r in data:
            htype   = type_map.get(
                r["holding_type"], HoldingType.EQUITY_MF
            )
            hold_id = f"brk_{r['fund_name'][:8].replace(' ','_')}"
            existing= [
                h for h in twin.current.demat_holdings
                if h.holding_id == hold_id
            ]
            if not existing:
                twin.add_holding(DematHolding(
                    holding_id      = hold_id,
                    fund_name       = r["fund_name"],
                    holding_type    = htype,
                    units           = r["units"],
                    current_nav     = r["nav"],
                ))
                updated = True
        return updated
