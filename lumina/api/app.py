"""
LUMINA FastAPI Application
Entry point. Wires OS + DB + Routes together.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lumina.config.settings import settings
from lumina.packages.financial_os.financial_os import FinancialOS
from lumina.observability.logging import configure_logging, get_logger
from lumina.persistence.database import init_db
from lumina.persistence.twin_repository import TwinRepository

configure_logging(level=settings.log_level, json_output=settings.is_production)
logger = get_logger("lumina.api.app")

# Singletons
financial_os = FinancialOS()
twin_repo    = TwinRepository()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("lumina.starting", version=settings.app_version)
    init_db()
    logger.info("lumina.ready", host=settings.api_host, port=settings.api_port)
    yield
    # Shutdown
    logger.info("lumina.stopping")


app = FastAPI(
    title       = settings.app_name,
    version     = settings.app_version,
    description = "Financial Operating System — consented, auditable, composable.",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

from lumina.api.routes import router
app.include_router(router)


@app.get("/")
def root():
    return {
        "name":    settings.app_name,
        "version": settings.app_version,
        "docs":    "/docs",
        "health":  "/api/v1/health",
    }
