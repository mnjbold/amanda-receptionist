"""Telnyx Webhook Handler for Amanda Receptionist"""

import logging
import json
import base64
from typing import Any

import telnyx
from fastapi import APIRouter, Request, BackgroundTasks

from config import settings
from telnyx_client import (
    answer_call, hang_up, speak, gather_using_ai, transfer_call,
)
from receptionist import (
    GREETING, INTENT_PARAMETERS, route_transfer, summarize_call,
    TRANSFERRING_MESSAGE, NO_TRANSFER_MESSAGE,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Ed25519 Signature Verification ──

def verify_telnyx_signature(payload: bytes, signature: str,
                            timestamp: str) -> bool:
    """Verify Telnyx Ed25519 webhook signature. Returns True if valid."""
    if not settings.verify_webhook:
        logger.debug("Webhook verification disabled — skipping")
        return True
    if not settings.telnyx_public_key:
        logger.warning("TELNYX_PUBLIC_KEY not set — signature check skipped")
        return True
    try:
        # Convert the timestamp str to int for construct_event
        ts = int(timestamp)
        telnyx.Webhook.construct_event(
            payload, signature, ts, settings.telnyx_public_key,
        )
        return True
    except Exception as e:
        logger.error("Ed25519 signature verification failed: %s", e)
        return False


# ── Helpers ──

def _extract_call_id(data: dict) -> str:
    """Safely extract call_control_id from webhook payload."""
    try:
        return data["payload"]["call_control_id"]
    except (KeyError, TypeError):
        return ""


def _extract_gather_result(data: dict) -> dict:
    """Safely extract gather result from webhook payload."""
    try:
        return data["payload"].get("result", {})
    except (KeyError, TypeError):
        return {}


# ── Event Handlers ──

async def handle_call_initiated(data: dict):
    """Answer incoming call immediately."""
    call_id = _extract_call_id(data)
    if not call_id:
        logger.error("call.initiated: no call_control_id in payload")
        return
    logger.info("📞 Incoming call %s — answering", call_id[:12])
    result = await answer_call(call_id)
    if not result.get("ok"):
        logger.error("answer_call failed for %s: %s", call_id[:12], result.get("error", "unknown"))


async def handle_call_answered(data: dict):
    """Call answered — greet and start AI gather."""
    call_id = _extract_call_id(data)
    if not call_id:
        logger.error("call.answered: no call_control_id")
        return
    logger.info("✅ Call %s answered — starting AI gather", call_id[:12])

    # Step 1: Greet with TTS
    greet_result = await speak(call_id, GREETING)
    if not greet_result.get("ok"):
        logger.error("speak failed for %s: %s", call_id[:12], greet_result.get("error", "unknown"))
        # Continue anyway — gather_using_ai has its own greeting

    # Step 2: Start AI gather (natural conversation)
    gather_result = await gather_using_ai(call_id, GREETING, INTENT_PARAMETERS)
    if not gather_result.get("ok"):
        logger.error("gather_using_ai failed for %s: %s", call_id[:12], gather_result.get("error", "unknown"))
        await speak(call_id, "I'm sorry, I'm having trouble understanding. Let me connect you to someone.")
        await _transfer_or_fallback(call_id, {})


async def handle_gather_ended(data: dict):
    """Gather result received — route the call."""
    call_id = _extract_call_id(data)
    result = _extract_gather_result(data)
    if not call_id:
        logger.error("call.gather.ended: no call_control_id")
        return

    logger.info("🎯 Gather result for %s: %s", call_id[:12], json.dumps(result, default=str))

    destination = route_transfer(result)

    if destination:
        logger.info("🔄 Transferring %s → %s", call_id[:12], destination)
        await speak(call_id, TRANSFERRING_MESSAGE)
        transfer_result = await transfer_call(call_id, destination)
        if not transfer_result.get("ok"):
            logger.error("transfer failed: %s", transfer_result.get("error", "unknown"))
            await speak(call_id, "I'm sorry, the transfer didn't go through. I'll make sure someone calls you back.")
    else:
        logger.info("ℹ️ No transfer destination — taking message")
        await speak(call_id, NO_TRANSFER_MESSAGE)

    # Log the call summary
    summary = summarize_call(result)
    logger.info("📋 Call summary: %s", summary)


async def handle_call_hangup(data: dict):
    """Call ended — cleanup."""
    call_id = _extract_call_id(data)
    logger.info("🔚 Call %s ended", call_id[:12] if call_id else "unknown")


# ── Transfer Fallback ──

async def _transfer_or_fallback(call_id: str, result: dict):
    """Attempt transfer; if fails, deliver fallback message."""
    destination = route_transfer(result) or settings.transfer_default or settings.transfer_jewel
    if destination:
        await speak(call_id, "Let me connect you now.")
        transfer_result = await transfer_call(call_id, destination)
        if transfer_result.get("ok"):
            return
    await speak(call_id, NO_TRANSFER_MESSAGE)
    await hang_up(call_id)


# ── Main Webhook Endpoint ──

@router.post("/webhooks")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive and process Telnyx webhook events.
    Signature is verified synchronously; processing happens in background.
    """
    # Read body once
    body = await request.body()

    # Verify signature
    sig = request.headers.get("Telnyx-Signature-Ed25519", "")
    ts = request.headers.get("Telnyx-Timestamp", "")
    if not verify_telnyx_signature(body, sig, ts):
        return {"status": "signature_invalid"}

    # Parse JSON
    try:
        payload = json.loads(body)
        data = payload.get("data", {})
        event_type = data.get("event_type", "unknown")
    except json.JSONDecodeError:
        logger.error("Failed to parse webhook body")
        return {"status": "bad_json"}

    logger.debug("Received event: %s", event_type)

    # Dispatch to handler (background, so we return 200 immediately)
    event_handlers = {
        "call.initiated": handle_call_initiated,
        "call.answered": handle_call_answered,
        "call.gather.ended": handle_gather_ended,
        "call.hangup": handle_call_hangup,
    }

    handler = event_handlers.get(event_type)
    if handler:
        background_tasks.add_task(handler, data)
    else:
        logger.debug("Unhandled event type: %s", event_type)

    return {"status": "ok"}
