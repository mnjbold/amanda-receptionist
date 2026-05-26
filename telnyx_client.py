"""Telnyx Async API Client for Amanda Receptionist"""

import logging
import httpx
from typing import Optional, Any

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.telnyx.com/v2"

# ── reusable header factory ──
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.telnyx_api_key}",
        "Content-Type": "application/json",
    }


async def _post(path: str, body: dict) -> dict[str, Any]:
    """POST to Telnyx API. Returns parsed JSON or structured error."""
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(url, json=body, headers=_headers())
            r.raise_for_status()
            return {"ok": True, "data": r.json().get("data", r.json())}
        except httpx.HTTPStatusError as e:
            logger.error("Telnyx HTTP %s %s → %s", e.response.status_code, path, e.response.text[:400])
            return {"ok": False, "status": e.response.status_code, "error": e.response.text[:400], "telnyx_error": True}
        except httpx.RequestError as e:
            logger.error("Telnyx request error %s → %s", path, e)
            return {"ok": False, "error": str(e), "telnyx_error": False}


# ── Call Control Actions ──

async def answer_call(call_control_id: str) -> dict:
    """Answer an incoming call."""
    return await _post(f"/calls/{call_control_id}/actions/answer", {})


async def hang_up(call_control_id: str) -> dict:
    """Hang up a call."""
    return await _post(f"/calls/{call_control_id}/actions/hangup", {})


async def speak(call_control_id: str, text: str, voice: str = None) -> dict:
    """Speak text to the caller."""
    voice = voice or settings.receptionist_voice
    return await _post(f"/calls/{call_control_id}/actions/speak", {
        "payload": text,
        "voice": voice,
        "language": "en-US",
    })


async def gather_using_ai(call_control_id: str, greeting: str, parameters: dict,
                          timeout_ms: int = None) -> dict:
    """AI-powered natural language gather."""
    timeout_ms = timeout_ms or settings.gather_timeout
    return await _post(f"/calls/{call_control_id}/actions/gather_using_ai", {
        "greeting": greeting,
        "parameters": parameters,
        "voice": settings.receptionist_voice,
        "client_state": "",
        "command_id": "",
    })


async def transfer_call(call_control_id: str, to: str, from_: str = None) -> dict:
    """Transfer a call to another number."""
    body = {"to": to}
    if from_:
        body["from"] = from_
    return await _post(f"/calls/{call_control_id}/actions/transfer", body)


async def start_ai_assistant(call_control_id: str, assistant_id: str) -> dict:
    """Attach a pre-built AI assistant to the call."""
    return await _post(f"/calls/{call_control_id}/actions/ai_assistant_start", {
        "assistant": {"id": assistant_id}
    })


async def stop_ai_assistant(call_control_id: str) -> dict:
    """Stop the AI assistant on a call."""
    return await _post(f"/calls/{call_control_id}/actions/ai_assistant_stop", {})


async def start_transcription(call_control_id: str, engine: str = "Deepgram") -> dict:
    """Start real-time transcription."""
    return await _post(f"/calls/{call_control_id}/actions/transcription_start", {
        "transcription_engine": engine,
        "language": "en",
    })


async def start_streaming(call_control_id: str, stream_url: str,
                          codec: str = "L16") -> dict:
    """Start media streaming to a WebSocket."""
    return await _post(f"/calls/{call_control_id}/actions/streaming_start", {
        "stream_url": stream_url,
        "stream_track": "both_tracks",
        "stream_bidirectional_mode": "rtp",
        "stream_bidirectional_codec": codec,
    })


# ── Outbound Dial ──

async def dial_outbound(to: str, from_: str, webhook_url: str,
                        connection_id: str = None) -> dict:
    """Initiate an outbound call."""
    body = {
        "to": to,
        "from": from_,
        "webhook_url": webhook_url,
    }
    if connection_id:
        body["connection_id"] = connection_id
    return await _post("/calls", body)


# ── Number Provisioning ──

async def search_numbers(area_code: str = None, npa_nxx: str = None,
                         features: list = None) -> dict:
    """Search available phone numbers."""
    params = {"filter[features][]": features or ["voice", "sms"]}
    if area_code:
        params["filter[area_code]"] = area_code
    if npa_nxx:
        params["filter[npa_nxx]"] = npa_nxx
    url = f"{BASE_URL}/available_phone_numbers"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, params=params, headers=_headers())
            r.raise_for_status()
            return {"ok": True, "data": r.json().get("data", [])}
        except Exception as e:
            return {"ok": False, "error": str(e)}


async def buy_number(phone_number: str) -> dict:
    """Purchase a phone number."""
    return await _post("/number_orders", {
        "phone_numbers": [{"phone_number": phone_number}]
    })


async def create_call_control_app(name: str, webhook_url: str,
                                  first_command_timeout: bool = True,
                                  timeout_secs: int = 30) -> dict:
    """Create a Telnyx Call Control Application."""
    return await _post("/call_control_applications", {
        "application_name": name,
        "webhook_event_url": webhook_url,
        "first_command_timeout": first_command_timeout,
        "first_command_timeout_secs": timeout_secs,
    })


async def get_phone_number(number_id: str) -> dict:
    """Get phone number details by Telnyx numeric ID."""
    url = f"{BASE_URL}/phone_numbers/{number_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url, headers=_headers())
            r.raise_for_status()
            return {"ok": True, "data": r.json().get("data", {})}
        except Exception as e:
            return {"ok": False, "error": str(e)}


async def reassign_number(number_id: str, connection_id: str) -> dict:
    """Reassign a phone number to a new connection (Call Control App)."""
    url = f"{BASE_URL}/phone_numbers/{number_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.patch(url, json={"connection_id": connection_id},
                                   headers=_headers())
            r.raise_for_status()
            return {"ok": True, "data": r.json().get("data", {})}
        except Exception as e:
            return {"ok": False, "error": str(e)}
