# -*- coding: utf-8 -*-
"""
Configuration for API Setu / ESIC (Employees' State Insurance Corporation) Verification.
Follows environment-driven 12-factor pattern without hardcoding secrets.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ESICVerificationConfig:
    """
    Encapsulates connection parameters for API Setu ESIC Verification.
    Manages both official endpoints: Health Passbook and Pehchan Card.
    """
    enabled: bool = False
    environment: str = "sandbox"          # "sandbox" or "production"
    base_url: str = "https://sandbox.api-setu.in"
    api_key: str = ""
    client_id: str = "in.gov.sandbox"
    timeout_seconds: int = 10

    # Official endpoint paths
    health_passbook_path: str = "/certificate/v3/esic/esich"
    pehchan_card_path: str = "/certificate/v3/esic/phcrd"

    @property
    def health_passbook_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.health_passbook_path}"

    @property
    def pehchan_card_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.pehchan_card_path}"

    def is_configured(self) -> bool:
        """
        Checks if ESIC verification is enabled and configured with an API key and client ID.
        """
        return bool(self.enabled and self.api_key.strip() and self.client_id.strip())

    @classmethod
    def from_env(cls) -> "ESICVerificationConfig":
        """
        Loads configuration from process environment variables.
        """
        enabled_val = os.environ.get("ESIC_VERIFICATION_ENABLED", "false").strip().lower()
        enabled = enabled_val in ("true", "1", "yes", "on")

        env_type = os.environ.get("ESIC_VERIFICATION_ENV", "sandbox").strip().lower()
        base_url = os.environ.get("ESIC_VERIFICATION_BASE_URL", "https://sandbox.api-setu.in").strip()
        api_key = os.environ.get("ESIC_VERIFICATION_API_KEY", "").strip()
        client_id = os.environ.get("ESIC_VERIFICATION_CLIENT_ID", "in.gov.sandbox").strip()

        try:
            timeout_sec = int(os.environ.get("ESIC_VERIFICATION_TIMEOUT_SECONDS", "10").strip())
        except ValueError:
            timeout_sec = 10

        return cls(
            enabled=enabled,
            environment=env_type,
            base_url=base_url,
            api_key=api_key,
            client_id=client_id,
            timeout_seconds=timeout_sec,
        )
