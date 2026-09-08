# -*- coding: utf-8 -*-
"""
DigiLocker / API Setu Sandbox HTTP Client.
Performs real HTTP network calls against the official sandbox endpoints.
Includes:
- PKCE Authorization Code generation and redirect URL construction
- Token exchange with client secret and code_verifier
- User profile retrieval
- Document inventory and pulling (PDF & XML)
- Token revocation
- Secret redaction on all network errors and logs
"""

import base64
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

from .audit import DigiLockerAuditLogger, default_audit_logger, hash_token
from .config import DigiLockerConfig
from .models import (
    DigiLockerDocumentItem,
    DigiLockerPulledDocument,
    DigiLockerTokenResponse,
    DigiLockerUserDetails,
)
from .pkce import generate_code_challenge, generate_code_verifier, generate_state
from .xml_parser import parse_pull_doc_response


class DigiLockerClientError(Exception):
    """Base exception for DigiLocker HTTP client operations."""
    pass


class DigiLockerAuthError(DigiLockerClientError):
    """Raised when authentication or authorization fails."""
    pass


class DigiLockerNetworkError(DigiLockerClientError):
    """Raised on network transport errors or timeouts."""
    pass


class DigiLockerSandboxClient:
    """
    Production-ready HTTP client for DigiLocker / API Setu Sandbox.
    Performs real requests with configurable timeouts, SSL verification,
    and automatic secret redaction.
    """
    def __init__(
        self,
        config: Optional[DigiLockerConfig] = None,
        audit_logger: Optional[DigiLockerAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or DigiLockerConfig.from_env()
        self.audit_logger = audit_logger or default_audit_logger
        self.session = session or requests.Session()

    def get_authorization_url(
        self,
        state: Optional[str] = None,
        code_verifier: Optional[str] = None,
        scope: str = "openid profile",
    ) -> Dict[str, str]:
        """
        Constructs the official OAuth 2.0 PKCE authorization redirect URL.
        Returns:
            {
                "url": authorization redirect URL,
                "state": CSRF state token,
                "code_verifier": generated verifier (must be saved to exchange code),
                "code_challenge": S256 challenge,
            }
        """
        state_token = state or generate_state()
        verifier = code_verifier or generate_code_verifier()
        challenge = generate_code_challenge(verifier)

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "state": state_token,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": scope,
        }

        query_string = urllib.parse.urlencode(params)
        auth_url = f"{self.config.authorize_url}?{query_string}"

        self.audit_logger.log(
            event_type="OAUTH_AUTHORIZE_INITIATED",
            status="SUCCESS",
            trace_id=state_token,
            details={
                "redirect_uri": self.config.redirect_uri,
                "client_id": self.config.client_id,
                "code_challenge_method": "S256",
            },
        )

        return {
            "url": auth_url,
            "state": state_token,
            "code_verifier": verifier,
            "code_challenge": challenge,
        }

    def exchange_code(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: Optional[str] = None,
    ) -> DigiLockerTokenResponse:
        """
        Exchanges an authorization code for an access token using PKCE verifier.
        Makes real HTTP POST to token endpoint.
        """
        if not code or not code.strip():
            raise DigiLockerAuthError("Authorization code must not be empty")
        if not code_verifier or not code_verifier.strip():
            raise DigiLockerAuthError("PKCE code_verifier must not be empty")

        payload = {
            "grant_type": "authorization_code",
            "code": code.strip(),
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "redirect_uri": redirect_uri or self.config.redirect_uri,
            "code_verifier": code_verifier.strip(),
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            resp = self.session.post(
                self.config.token_url,
                data=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        except requests.exceptions.Timeout as te:
            self.audit_logger.log(
                event_type="OAUTH_TOKEN_EXCHANGED",
                status="TIMEOUT",
                details={"url": self.config.token_url},
            )
            raise DigiLockerNetworkError("Timeout communicating with DigiLocker token endpoint") from te
        except requests.exceptions.RequestException as re:
            self.audit_logger.log(
                event_type="OAUTH_TOKEN_EXCHANGED",
                status="NETWORK_ERROR",
                details={"url": self.config.token_url},
            )
            raise DigiLockerNetworkError(f"Network error during token exchange: {re}") from re

        if resp.status_code != 200:
            self.audit_logger.log(
                event_type="OAUTH_TOKEN_EXCHANGED",
                status="FAILED",
                details={"status_code": resp.status_code},
            )
            raise DigiLockerAuthError(
                f"Token exchange failed (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        try:
            data = resp.json()
        except Exception as e:
            raise DigiLockerClientError("Invalid JSON returned by DigiLocker token endpoint") from e

        token_response = DigiLockerTokenResponse.from_dict(data)

        self.audit_logger.log(
            event_type="OAUTH_TOKEN_EXCHANGED",
            status="SUCCESS",
            details={
                "token_type": token_response.token_type,
                "expires_in": token_response.expires_in,
                "scope": token_response.scope,
                "access_token_hash": hash_token(token_response.access_token),
            },
        )

        return token_response

    def get_user_details(self, access_token: str) -> DigiLockerUserDetails:
        """
        Fetches authenticated user details from DigiLocker /user endpoint.
        """
        if not access_token:
            raise DigiLockerAuthError("Access token required to fetch user details")

        headers = {
            "Authorization": f"Bearer {access_token.strip()}",
            "Accept": "application/json",
        }

        try:
            resp = self.session.get(
                self.config.user_url,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        except requests.exceptions.RequestException as re:
            raise DigiLockerNetworkError(f"Failed to fetch user details: {re}") from re

        if resp.status_code != 200:
            raise DigiLockerClientError(
                f"User details request failed (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        try:
            data = resp.json()
        except Exception as e:
            raise DigiLockerClientError("Invalid JSON returned by DigiLocker user endpoint") from e

        user = DigiLockerUserDetails.from_dict(data)

        self.audit_logger.log(
            event_type="USER_DETAILS_FETCHED",
            status="SUCCESS",
            details={
                "digilocker_id": user.digilocker_id,
                "name": user.name,
                "token_hash": hash_token(access_token),
            },
        )

        return user

    def get_issued_documents(self, access_token: str) -> List[DigiLockerDocumentItem]:
        """
        Retrieves list of issued certificates and documents in the user's DigiLocker.
        """
        if not access_token:
            raise DigiLockerAuthError("Access token required to fetch issued documents")

        headers = {
            "Authorization": f"Bearer {access_token.strip()}",
            "Accept": "application/json",
        }

        try:
            resp = self.session.get(
                self.config.issued_documents_url,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        except requests.exceptions.RequestException as re:
            raise DigiLockerNetworkError(f"Failed to fetch issued documents: {re}") from re

        if resp.status_code != 200:
            raise DigiLockerClientError(
                f"Document listing failed (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        try:
            data = resp.json()
        except Exception as e:
            raise DigiLockerClientError("Invalid JSON returned by DigiLocker documents endpoint") from e

        items_raw = data.get("items") or data.get("documents") or []
        if isinstance(data, list):
            items_raw = data

        items = [DigiLockerDocumentItem.from_dict(item) for item in items_raw if isinstance(item, dict)]

        self.audit_logger.log(
            event_type="DOCUMENT_LIST_FETCHED",
            status="SUCCESS",
            details={
                "document_count": len(items),
                "token_hash": hash_token(access_token),
            },
        )

        return items

    def pull_document(
        self,
        access_token: str,
        doc_uri: str,
        doc_type: Optional[str] = None,
    ) -> DigiLockerPulledDocument:
        """
        Pulls document payload from DigiLocker / API Setu sandbox by URI.
        Parses XML payload and embedded base64 PDF.
        """
        if not access_token:
            raise DigiLockerAuthError("Access token required to pull document")
        if not doc_uri:
            raise ValueError("Document URI must not be empty")

        headers = {
            "Authorization": f"Bearer {access_token.strip()}",
            "Accept": "application/xml, application/json, application/pdf",
        }

        payload = {
            "uri": doc_uri,
            "doc_type": doc_type or "DEFAULT",
        }

        try:
            resp = self.session.post(
                self.config.pull_document_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        except requests.exceptions.RequestException as re:
            raise DigiLockerNetworkError(f"Failed to pull document '{doc_uri}': {re}") from re

        if resp.status_code != 200:
            raise DigiLockerClientError(
                f"Document pull failed (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        content_type = resp.headers.get("Content-Type", "")
        pdf_bytes: Optional[bytes] = None
        xml_content: Optional[str] = None
        parsed_cert = None
        metadata: Dict[str, Any] = {}

        if "pdf" in content_type:
            pdf_bytes = resp.content
            mime_type = "application/pdf"
        elif "xml" in content_type or resp.text.strip().startswith("<"):
            xml_content = resp.text
            mime_type = "application/xml"
            pdf_bytes, parsed_cert, metadata = parse_pull_doc_response(xml_content)
        else:
            # Fallback: check raw content bytes
            if resp.content.startswith(b"%PDF-"):
                pdf_bytes = resp.content
                mime_type = "application/pdf"
            else:
                xml_content = resp.text
                mime_type = "application/xml"
                try:
                    pdf_bytes, parsed_cert, metadata = parse_pull_doc_response(xml_content)
                except Exception:
                    pass

        pulled = DigiLockerPulledDocument(
            doc_uri=doc_uri,
            doc_type=doc_type or (parsed_cert.certificate_type if parsed_cert else "UNKNOWN"),
            mime_type=mime_type,
            pdf_content=pdf_bytes,
            xml_content=xml_content,
            certificate=parsed_cert,
            metadata=metadata,
        )

        self.audit_logger.log(
            event_type="DOCUMENT_PULLED",
            status="SUCCESS",
            details={
                "doc_uri": doc_uri,
                "has_pdf": pdf_bytes is not None,
                "has_cert": parsed_cert is not None,
                "cert_type": parsed_cert.certificate_type if parsed_cert else None,
                "token_hash": hash_token(access_token),
            },
        )

        return pulled

    def revoke_token(self, token: str) -> bool:
        """
        Revokes an issued access or refresh token.
        """
        if not token:
            return False

        payload = {
            "token": token.strip(),
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        try:
            resp = self.session.post(
                self.config.revoke_token_url,
                data=payload,
                timeout=self.config.timeout_seconds,
            )
            success = resp.status_code in (200, 204)
        except requests.exceptions.RequestException:
            success = False

        self.audit_logger.log(
            event_type="TOKEN_REVOKED",
            status="SUCCESS" if success else "FAILED",
            details={"token_hash": hash_token(token)},
        )

        return success
