"""Amanda — AI Receptionist for Bold Business
Telnyx-powered voice AI agent. Handles inbound calls, gathers intent, and transfers.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings
from webhooks import router as webhooks_router
from telnyx_client import dial_outbound

# ── Logging ──

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("amanda")


# ── Lifespan ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("👋 Amanda receptionist starting up — %s at %s",
                settings.business_name, settings.receptionist_name)
    yield
    logger.info("🛑 Amanda shutting down")


# ── App ──

app = FastAPI(
    title="Amanda — AI Receptionist",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)

# ── Public base URL (set via env var, Railway injects RAILWAY_PUBLIC_DOMAIN)
_base_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
BASE_URL = f"https://{_base_url}" if _base_url else os.environ.get("BASE_URL", "http://localhost:8000")


# ── Health ──

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "amanda-receptionist",
        "telnyx_configured": bool(settings.telnyx_api_key),
    }


# ── Outbound Call (optional API) ──

from pydantic import BaseModel


class OutboundCallRequest(BaseModel):
    to: str
    from_: str
    webhook_url: str | None = None


@app.post("/call")
async def outbound_call(req: OutboundCallRequest):
    """Initiate an outbound call. Amanda will greet and gather intent."""
    webhook = req.webhook_url or f"{BASE_URL}/webhooks"
    result = await dial_outbound(
        to=req.to,
        from_=req.from_,
        webhook_url=webhook,
    )
    if result.get("ok"):
        return {"status": "ok", "call": result.get("data")}
    return {"status": "error", "detail": result.get("error", "unknown")}


# ── Entrypoint ──

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=(settings.env == "development"),
    )
