"""Amanda Receptionist — call logic and routing"""

import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# ── Greeting Script ──

GREETING = (
    f"Hi there, this is {settings.receptionist_name} with {settings.business_name}. "
    "I'm the virtual receptionist. Who am I speaking with today, and how can I help you?"
)

# ── Gather Parameters ──

INTENT_PARAMETERS = {
    "type": "object",
    "properties": {
        "caller_name": {
            "type": "string",
            "description": "The caller's full name"
        },
        "reason": {
            "type": "string",
            "description": "Why they are calling — be specific"
        },
        "who_they_want": {
            "type": "string",
            "description": "Who they asked for by name or role (Jewel, owner, sales, support, etc.)"
        },
        "is_urgent": {
            "type": "boolean",
            "description": "True if the caller says it's urgent or uses urgent language"
        },
        "callback_number": {
            "type": "string",
            "description": "A phone number where they can be reached if the call drops"
        },
    },
    "required": ["caller_name", "reason"],
}


# ── Transfer Routing ──

def route_transfer(gather_result: dict) -> Optional[str]:
    """
    Determine transfer destination from gather result.
    Returns a phone number or None if no transfer is needed.
    """
    who = (gather_result.get("who_they_want") or "").lower()
    reason = (gather_result.get("reason") or "").lower()

    # Jewel-specific routing
    jewel_keywords = ["jewel", "owner", "ceo", "founder", "boss"]
    if any(kw in who for kw in jewel_keywords) and settings.transfer_jewel:
        return settings.transfer_jewel

    # Sales routing
    sales_keywords = ["sales", "pricing", "quote", "demo", "buy", "purchase", "billing"]
    if any(kw in who + " " + reason for kw in sales_keywords) and settings.transfer_sales:
        return settings.transfer_sales

    # Support routing
    support_keywords = ["support", "help", "issue", "problem", "bug", "broken", "error", "not working"]
    if any(kw in who + " " + reason for kw in support_keywords) and settings.transfer_support:
        return settings.transfer_support

    # If any of the specific destinations aren't set, fall back to transfer_default
    if settings.transfer_default:
        return settings.transfer_default

    # If no transfer destination is configured, fall back to Jewel
    if settings.transfer_jewel:
        return settings.transfer_jewel

    return None


# ── Message Templates ──

TRANSFERRING_MESSAGE = "Great, let me connect you now. One moment please."

NO_TRANSFER_MESSAGE = (
    "I wasn't able to connect you right now, but I've noted your details "
    "and someone will get back to you shortly. Is there anything else I can help with?"
)

HOLD_MESSAGE = "I'll check if they're available. Give me just a moment."


# ── Call Summary (for logging/dash) ──

def summarize_call(gather_result: dict) -> str:
    """Format a human-readable summary of the call."""
    name = gather_result.get("caller_name", "Unknown")
    reason = gather_result.get("reason", "No reason given")
    who = gather_result.get("who_they_want", "No specific person")
    urgent = "🚨 URGENT" if gather_result.get("is_urgent") else ""
    callback = gather_result.get("callback_number", "")

    lines = [
        f"📞 Call from: **{name}**",
        f"Reason: {reason}",
        f"Asked for: {who}",
    ]
    if urgent:
        lines.append(urgent)
    if callback:
        lines.append(f"Callback: {callback}")

    return "\n".join(lines)
