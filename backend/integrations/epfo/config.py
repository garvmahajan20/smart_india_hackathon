# -*- coding: utf-8 -*-
"""
Configuration for API Setu / EPFO (Employees' Provident Fund Organisation) Verification.
Follows environment-driven 12-factor pattern without hardcoding secrets.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class EPFOVerificationConfig:
    """
    Encapsulates all connection parameters for API Setu EPFO Verification.
    Manages all three official endpoints: UAN Card, Scheme Certificate, Pension Certificate.
    """
    enabled: bool = False
    environment: str = "sandbox"          # "sandbox" or "production"
    base_url: str = "https://sandbox.api-setu.in"
    api_key: str = ""
    client_id: str = "in.gov.sandbox"
    timeout_seconds: int = 10

    # Official endpoint paths
    uan_card_path: str = "/certificate/v3/epfindia/uncrd"
    scheme_cert_path: str = "/certificate/v3/epfindia/epfsc"
    pension_cert_path: str = "/certificate/v3/epfindia/pecer"

    @property
    def uan_card_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.uan_card_path}"

    @property
    def scheme_cert_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.scheme_cert_path}"

    @property
    def pension_cert_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.pension_cert_path}"

    def is_configured(self) -> bool:
        """
        Checks if EPFO verification is enabled and configured with an API key and client ID.
        """
        return bool(self.enabled and self.api_key.strip() and self.client_id.strip())

    @classmethod
    def from_env(cls) -> "EPFOVerificationConfig":
        """
        Loads configuration from process environment variables.
        """
        enabled_val = os.environ.get("EPFO_VERIFICATION_ENABLED", "false").strip().lower()
        enabled = enabled_val in ("true", "1", "yes", "on")

        env_type = os.environ.get("EPFO_VERIFICATION_ENV", "sandbox").strip().lower()
        base_url = os.environ.get("EPFO_VERIFICATION_BASE_URL", "https://sandbox.api-setu.in").strip()
        api_key = os.environ.get("EPFO_VERIFICATION_API_KEY", "").strip()
        client_id = os.environ.get("EPFO_VERIFICATION_CLIENT_ID", "in.gov.sandbox").strip()

        try:
            timeout_sec = int(os.environ.get("EPFO_VERIFICATION_TIMEOUT_SECONDS", "10").strip())
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
