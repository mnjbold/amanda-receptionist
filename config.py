"""Amanda Receptionist — Configuration"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    # Telnyx
    telnyx_api_key: str = os.environ.get("TELNYX_API_KEY", "")
    telnyx_public_key: str = os.environ.get("TELNYX_PUBLIC_KEY", "")

    # Server
    port: int = int(os.environ.get("PORT", "8000"))
    env: str = os.environ.get("ENV", "production")

    # Amanda — receptionist persona config
    business_name: str = os.environ.get("BUSINESS_NAME", "Bold Business")
    receptionist_name: str = os.environ.get("RECEPTIONIST_NAME", "Amanda")
    receptionist_voice: str = os.environ.get("RECEPTIONIST_VOICE", "Polly.Joanna")

    # Transfer destinations
    transfer_jewel: str = os.environ.get("TRANSFER_JEWEL", "+601121113249")
    transfer_sales: str = os.environ.get("TRANSFER_SALES", "")
    transfer_support: str = os.environ.get("TRANSFER_SUPPORT", "")
    transfer_default: str = os.environ.get("TRANSFER_DEFAULT", "")

    # Webhook signing (disable in dev)
    verify_webhook: bool = os.environ.get("VERIFY_WEBHOOK", "true").lower() == "true"

    # Gather AI config
    gather_timeout: int = int(os.environ.get("GATHER_TIMEOUT", "30000"))

    # Logging
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
