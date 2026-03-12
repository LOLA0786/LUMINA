from fastapi import FastAPI
from opentelemetry import trace
import sentry_sdk

sentry_sdk.init(dsn="...")  # will be in .env

app = FastAPI(title="LUMINA API", version="0.1")

@app.get("/health")
async def health():
    return {"status": "LUMINA is illuminating your wealth"}
