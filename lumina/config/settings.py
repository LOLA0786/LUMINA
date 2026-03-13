"""
LUMINA Configuration Management
No hardcoded values anywhere in the codebase.
All config comes from environment variables or .env file.

Usage anywhere in LUMINA:
    from lumina.config.settings import settings
    print(settings.app_name)
    print(settings.emergency_fund_months)
"""
from __future__ import annotations
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LuminaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────
    app_name: str                  = "LUMINA Financial OS"
    app_version: str               = "1.0.0"
    environment: str               = "development"   # development | staging | production
    debug: bool                    = False
    log_level: str                 = "INFO"

    # ── Financial rules (all tunable via env) ────────────────────
    emergency_fund_months: int     = 6        # months of expenses to keep liquid
    ltv_cap_pct: float             = 0.80     # RBI LTV cap
    max_foir_pct: float            = 0.50     # max EMI/income ratio
    comfortable_foir_pct: float    = 0.40     # comfortable EMI/income ratio
    income_multiplier_loan: int    = 60       # max loan = income × this
    equity_haircut_pct: float      = 0.80     # liquid value of equity MF
    single_action_limit_inr: float = 500_000  # ₹5L enhanced review threshold
    min_agent_confidence: float    = 0.60     # below this → advisory only
    concentration_limit_pct: float = 0.35     # max single asset % of portfolio

    # ── Tax (FY 2024-25) ─────────────────────────────────────────
    ltcg_exemption_inr: float      = 125_000  # ₹1.25L LTCG exemption
    std_deduction_old_inr: float   = 50_000
    std_deduction_new_inr: float   = 75_000
    max_80c_inr: float             = 150_000
    max_80d_inr: float             = 25_000
    max_nps_80ccd_inr: float       = 50_000

    # ── Database ─────────────────────────────────────────────────
    database_url: str              = "sqlite:///lumina.db"
    db_echo: bool                  = False

    # ── API ───────────────────────────────────────────────────────
    api_host: str                  = "0.0.0.0"
    api_port: int                  = 8000
    api_reload: bool               = True
    jwt_secret_key: str            = "change-this-in-production"
    jwt_algorithm: str             = "HS256"
    jwt_expire_minutes: int        = 60

    # ── PrivateVault governance ───────────────────────────────────
    governance_enabled: bool       = True
    merkle_log_enabled: bool       = True
    audit_retention_days: int      = 2555    # 7 years (SEBI requirement)

    # ── External feeds (future) ───────────────────────────────────
    market_feed_url: Optional[str] = None
    rbi_feed_url: Optional[str]    = None
    bank_webhook_secret: Optional[str] = None

    # ── Derived helpers ───────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache(maxsize=1)
def get_settings() -> LuminaSettings:
    """
    Cached settings singleton.
    Call get_settings() anywhere — returns same instance.
    Override in tests: get_settings.cache_clear()
    """
    return LuminaSettings()


# Module-level singleton for convenience
settings = get_settings()
