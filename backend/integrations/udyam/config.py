# -*- coding: utf-8 -*-
"""
Configuration for API Setu / MSME Udyam Certificate Verification.
Follows environment-driven 12-factor pattern without hardcoding secrets.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class UdyamVerificationConfig:
    """
    Encapsulates all connection parameters for API Setu Udyam Verification.
    """
    enabled: bool = False
    environment: str = "sandbox"          # "sandbox" or "production"
    base_url: str = "https://sandbox.api-setu.in"
    api_key: str = ""
    client_id: str = "in.gov.sandbox"
    timeout_seconds: int = 10
    endpoint_path: str = "/certificate/v3/msme/udcer"

    @property
    def endpoint_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.endpoint_path}"

    def is_configured(self) -> bool:
        """
        Checks if Udyam verification is enabled and configured with an API key and client ID.
        """
        return bool(self.enabled and self.api_key.strip() and self.client_id.strip())

    @classmethod
    def from_env(cls) -> "UdyamVerificationConfig":
        """
        Loads configuration from process environment variables.
        """
        enabled_val = os.environ.get("UDYAM_VERIFICATION_ENABLED", "false").strip().lower()
        enabled = enabled_val in ("true", "1", "yes", "on")

        env_type = os.environ.get("UDYAM_VERIFICATION_ENV", "sandbox").strip().lower()
        base_url = os.environ.get("UDYAM_VERIFICATION_BASE_URL", "https://sandbox.api-setu.in").strip()
        api_key = os.environ.get("UDYAM_VERIFICATION_API_KEY", "").strip()
        client_id = os.environ.get("UDYAM_VERIFICATION_CLIENT_ID", "in.gov.sandbox").strip()

        try:
            timeout_sec = int(os.environ.get("UDYAM_VERIFICATION_TIMEOUT_SECONDS", "10").strip())
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
