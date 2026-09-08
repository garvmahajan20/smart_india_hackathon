# -*- coding: utf-8 -*-
"""
Configuration for GSTINAPI (private GST provider).
Follows 12-factor environment configuration pattern.
Never hardcodes secrets or commits credentials.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class GSTINAPIConfig:
    """
    Configuration settings for GSTINAPI client.
    """
    api_key: str = ""
    base_url: str = "https://www.gstinapi.in"
    environment: str = "production"
    enabled: bool = True
    timeout_seconds: int = 10
    max_retries: int = 2
    retry_backoff_factor: float = 0.5
    cache_enabled: bool = True
    rate_limit_per_minute: int = 60
    test_gstin: str = "00AAAAA0000A1ZT"

    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key.strip())

    def auth_header(self) -> dict:
        if not self.is_configured():
            return {}
        return {"x-api-key": self.api_key}

    @classmethod
    def from_env(cls) -> "GSTINAPIConfig":
        """
        Loads configuration from environment variables without logging or leaking keys.
        """
        api_key = os.environ.get("GSTINAPI_API_KEY", "").strip()
        base_url = os.environ.get("GSTINAPI_BASE_URL", "https://www.gstinapi.in").strip().rstrip("/")
        enabled_str = os.environ.get("GSTINAPI_ENABLED", "").strip().lower()
        if enabled_str:
            enabled = enabled_str in ("true", "1", "yes", "on")
        else:
            enabled = bool(api_key)

        try:
            timeout_sec = int(os.environ.get("GSTINAPI_TIMEOUT_SECONDS", "10").strip())
        except ValueError:
            timeout_sec = 10

        try:
            max_retries = int(os.environ.get("GSTINAPI_MAX_RETRIES", "2").strip())
        except ValueError:
            max_retries = 2

        environment = os.environ.get("GSTINAPI_ENVIRONMENT", "production").strip() or "production"

        return cls(
            api_key=api_key,
            base_url=base_url or "https://www.gstinapi.in",
            environment=environment,
            enabled=enabled,
            timeout_seconds=timeout_sec,
            max_retries=max_retries,
        )
