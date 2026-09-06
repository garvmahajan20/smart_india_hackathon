# -*- coding: utf-8 -*-
"""
Configuration management for DigiLocker / API Setu Sandbox Integration.
Follows environment-driven 12-factor pattern without hardcoding secrets.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DigiLockerConfig:
    """
    Encapsulates all connection parameters and endpoints for DigiLocker sandbox/production.
    """
    enabled: bool = False
    environment: str = "sandbox"  # "sandbox" or "production"
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/api/v1/integrations/digilocker/callback"
    base_url: str = "https://sandbox.api-setu.in"
    timeout_seconds: int = 30

    # Custom endpoint overrides (if explicitly provided via environment)
    authorize_url_override: Optional[str] = None
    token_url_override: Optional[str] = None
    user_url_override: Optional[str] = None
    issued_documents_url_override: Optional[str] = None
    pull_document_url_override: Optional[str] = None
    revoke_token_url_override: Optional[str] = None

    @property
    def authorize_url(self) -> str:
        if self.authorize_url_override:
            return self.authorize_url_override
        b = self.base_url.rstrip("/")
        if "dev-meripehchaan" in b or "digitallocker" in b or b.endswith("/public"):
            return f"{b}/oauth2/1/authorize"
        return f"{b}/api/v1/digilocker/oauth/authorize"

    @property
    def token_url(self) -> str:
        if self.token_url_override:
            return self.token_url_override
        b = self.base_url.rstrip("/")
        if "dev-meripehchaan" in b or "digitallocker" in b or b.endswith("/public"):
            return f"{b}/oauth2/1/token"
        return f"{b}/api/v1/digilocker/oauth/token"

    @property
    def user_url(self) -> str:
        if self.user_url_override:
            return self.user_url_override
        b = self.base_url.rstrip("/")
        if "dev-meripehchaan" in b or "digitallocker" in b or b.endswith("/public"):
            return f"{b}/oauth2/1/user"
        return f"{b}/api/v1/digilocker/user"

    @property
    def issued_documents_url(self) -> str:
        if self.issued_documents_url_override:
            return self.issued_documents_url_override
        b = self.base_url.rstrip("/")
        if "dev-meripehchaan" in b or "digitallocker" in b or b.endswith("/public"):
            return f"{b}/oauth2/1/files/issued"
        return f"{b}/api/v1/digilocker/documents/issued"

    @property
    def pull_document_url(self) -> str:
        if self.pull_document_url_override:
            return self.pull_document_url_override
        b = self.base_url.rstrip("/")
        if "dev-meripehchaan" in b or "digitallocker" in b or b.endswith("/public"):
            return f"{b}/oauth2/1/pull/pulldocument"
        return f"{b}/api/v1/digilocker/documents/pull"

    @property
    def revoke_token_url(self) -> str:
        if self.revoke_token_url_override:
            return self.revoke_token_url_override
        b = self.base_url.rstrip("/")
        if "dev-meripehchaan" in b or "digitallocker" in b or b.endswith("/public"):
            return f"{b}/oauth2/1/revoke"
        return f"{b}/api/v1/digilocker/oauth/revoke"

    def is_configured(self) -> bool:
        """
        Validates if DigiLocker integration is fully enabled and configured with required credentials.
        """
        return bool(self.enabled and self.client_id.strip() and self.client_secret.strip())

    @classmethod
    def from_env(cls) -> "DigiLockerConfig":
        """
        Constructs configuration from environment variables.
        """
        enabled_val = os.environ.get("DIGILOCKER_ENABLED", "false").strip().lower()
        enabled = enabled_val in ("true", "1", "yes", "on")

        env_type = os.environ.get("DIGILOCKER_ENV", "sandbox").strip().lower()
        client_id = os.environ.get("DIGILOCKER_CLIENT_ID", "").strip()
        client_secret = os.environ.get("DIGILOCKER_CLIENT_SECRET", "").strip()
        redirect_uri = os.environ.get(
            "DIGILOCKER_REDIRECT_URI",
            "http://localhost:8000/api/v1/integrations/digilocker/callback"
        ).strip()
        base_url = os.environ.get("DIGILOCKER_BASE_URL", "https://sandbox.api-setu.in").strip()

        try:
            timeout_seconds = int(os.environ.get("DIGILOCKER_TIMEOUT_SECONDS", "30").strip())
        except ValueError:
            timeout_seconds = 30

        return cls(
            enabled=enabled,
            environment=env_type,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            authorize_url_override=os.environ.get("DIGILOCKER_AUTHORIZE_URL"),
            token_url_override=os.environ.get("DIGILOCKER_TOKEN_URL"),
            user_url_override=os.environ.get("DIGILOCKER_USER_URL"),
            issued_documents_url_override=os.environ.get("DIGILOCKER_ISSUED_DOCUMENTS_URL"),
            pull_document_url_override=os.environ.get("DIGILOCKER_PULL_DOCUMENT_URL"),
            revoke_token_url_override=os.environ.get("DIGILOCKER_REVOKE_TOKEN_URL"),
        )
