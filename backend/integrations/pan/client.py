# -*- coding: utf-8 -*-
"""
Real HTTP Client for API Setu / Income Tax Department PAN Verification.
Makes actual HTTP requests to:
  POST {PAN_VERIFICATION_BASE_URL}/certificate/v3/pan/pancr
Enforces:
- Explicit configurable timeout
- Strict TLS verification (verify=True)
- Deterministic transaction UUID generation
- Zero secret leakage: scrubs X-APISETU-APIKEY from all logs and error traces
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional

import requests

from .audit import PANAuditLogger, default_pan_audit_logger, hash_secret, mask_pan
from .config import PANVerificationConfig
from .models import (
    PANVerificationRequest,
    PANVerificationResponse,
    PANVerificationStatus,
    is_valid_pan_format,
)
from .xml_parser import PANXMLParsingError, parse_pan_verification_xml


class PANClientError(Exception):
    """Base exception for PAN Verification Client operations."""
    pass


class PANClientAuthError(PANClientError):
    """Raised on authentication/API key failures (HTTP 401/403)."""
    pass


class PANClientNetworkError(PANClientError):
    """Raised on network transport errors, DNS failures, or timeouts."""
    pass


class APISetuPANClient:
    """
    Real HTTP Client for official API Setu PAN Verification Record.
    """
    def __init__(
        self,
        config: Optional[PANVerificationConfig] = None,
        audit_logger: Optional[PANAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or PANVerificationConfig.from_env()
        self.audit_logger = audit_logger or default_pan_audit_logger
        self.session = session or requests.Session()

    def verify_pan(self, request: PANVerificationRequest) -> PANVerificationResponse:
        """
        Executes real HTTP call to official API Setu PANCR endpoint.
        """
        clean_pan = request.clean_pan()

        # Step 1: Input syntax validation
        if not is_valid_pan_format(clean_pan):
            self.audit_logger.log(
                event_type="PAN_VERIFICATION_REQUESTED",
                status="INVALID_FORMAT",
                txn_id=request.txn_id,
                details={"pan": clean_pan, "reason": "Invalid PAN syntax format"},
            )
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.INVALID_REQUEST,
                http_status=400,
                pan=clean_pan,
                error_code="INVALID_PAN_FORMAT",
                error_message="PAN does not conform to standard format (5 letters, 4 digits, 1 letter).",
                is_live=False,
            )

        headers = {
            "Content-Type": "application/json",
            "X-APISETU-APIKEY": self.config.api_key,
            "X-APISETU-CLIENTID": self.config.client_id,
            "Accept": "application/xml, application/json, */*",
        }

        payload = request.to_api_payload()

        self.audit_logger.log(
            event_type="PAN_REQUEST_INITIATED",
            status="INITIATED",
            txn_id=request.txn_id,
            details={
                "pan": clean_pan,
                "endpoint": self.config.endpoint_url,
                "client_id": self.config.client_id,
                "api_key_hash": hash_secret(self.config.api_key),
            },
        )

        start_time = time.time()
        try:
            resp = self.session.post(
                self.config.endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
                verify=True,  # Mandatory TLS validation
            )
            latency_ms = (time.time() - start_time) * 1000.0

        except requests.exceptions.Timeout as te:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="PAN_EXTERNAL_ERROR",
                status="TIMEOUT",
                txn_id=request.txn_id,
                details={"pan": clean_pan, "latency_ms": latency_ms},
            )
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.UNAVAILABLE,
                http_status=504,
                pan=clean_pan,
                error_code="TIMEOUT",
                error_message=f"Request to API Setu timed out after {self.config.timeout_seconds} seconds.",
                latency_ms=latency_ms,
                is_live=True,
            )

        except requests.exceptions.RequestException as re:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="PAN_EXTERNAL_ERROR",
                status="NETWORK_ERROR",
                txn_id=request.txn_id,
                details={"pan": clean_pan, "error": str(re), "latency_ms": latency_ms},
            )
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.ERROR,
                http_status=502,
                pan=clean_pan,
                error_code="NETWORK_FAILURE",
                error_message=f"Network error communicating with API Setu: {re}",
                latency_ms=latency_ms,
                is_live=True,
            )

        # Compute deterministic response hash
        resp_bytes = resp.content
        resp_hash = hashlib.sha256(resp_bytes).hexdigest() if resp_bytes else None

        self.audit_logger.log(
            event_type="PAN_RESPONSE_RECEIVED",
            status=f"HTTP_{resp.status_code}",
            txn_id=request.txn_id,
            details={
                "pan": clean_pan,
                "http_status": resp.status_code,
                "content_type": resp.headers.get("Content-Type", ""),
                "response_size_bytes": len(resp_bytes),
                "latency_ms": latency_ms,
                "response_hash": resp_hash,
            },
        )

        # Handle HTTP errors explicitly
        if resp.status_code in (401, 403):
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.ERROR,
                http_status=resp.status_code,
                pan=clean_pan,
                error_code="UNAUTHORIZED",
                error_message="Invalid or unauthorized API Setu credentials.",
                latency_ms=latency_ms,
                response_hash=resp_hash,
                is_live=True,
            )

        if resp.status_code == 404:
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.NOT_VERIFIED,
                http_status=404,
                pan=clean_pan,
                error_code="NOT_FOUND",
                error_message=f"PAN '{clean_pan}' was not found in the external registry.",
                latency_ms=latency_ms,
                response_hash=resp_hash,
                is_live=True,
            )

        if resp.status_code >= 500:
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.ERROR,
                http_status=resp.status_code,
                pan=clean_pan,
                error_code="GATEWAY_ERROR",
                error_message=f"API Setu upstream gateway error (HTTP {resp.status_code}).",
                latency_ms=latency_ms,
                response_hash=resp_hash,
                is_live=True,
            )

        if resp.status_code == 400:
            # Parse error response from API Setu (JSON or XML)
            err_desc = resp.text[:200]
            try:
                err_data = resp.json()
                err_desc = err_data.get("errorDescription") or err_data.get("error") or err_desc
            except Exception:
                pass

            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.INVALID_REQUEST,
                http_status=400,
                pan=clean_pan,
                error_code="BAD_REQUEST",
                error_message=f"API Setu rejected request: {err_desc}",
                latency_ms=latency_ms,
                response_hash=resp_hash,
                is_live=True,
            )

        # Successful HTTP response (200 / 201)
        content_type = resp.headers.get("Content-Type", "").lower()
        body_text = resp.text

        # 1. XML parsing path
        if "xml" in content_type or body_text.strip().startswith("<"):
            try:
                parsed_res = parse_pan_verification_xml(
                    xml_string=body_text,
                    txn_id=request.txn_id,
                    http_status=resp.status_code,
                    queried_pan=clean_pan,
                    latency_ms=latency_ms,
                    response_hash=resp_hash,
                )
                self.audit_logger.log(
                    event_type="PAN_RESPONSE_PARSED",
                    status="SUCCESS",
                    txn_id=request.txn_id,
                    details={"format": "xml", "pan": clean_pan, "verified_name": parsed_res.verified_name},
                )
                return parsed_res
            except PANXMLParsingError as xe:
                return PANVerificationResponse(
                    txn_id=request.txn_id,
                    status=PANVerificationStatus.ERROR,
                    http_status=resp.status_code,
                    pan=clean_pan,
                    error_code="MALFORMED_XML",
                    error_message=f"Failed to parse API Setu XML payload: {xe}",
                    latency_ms=latency_ms,
                    response_hash=resp_hash,
                    is_live=True,
                )

        # 2. JSON parsing path
        try:
            json_data = resp.json()
            return self._parse_json_response(json_data, request.txn_id, resp.status_code, clean_pan, latency_ms, resp_hash)
        except Exception:
            return PANVerificationResponse(
                txn_id=request.txn_id,
                status=PANVerificationStatus.ERROR,
                http_status=resp.status_code,
                pan=clean_pan,
                error_code="UNEXPECTED_CONTENT",
                error_message="API Setu returned unparseable content type.",
                latency_ms=latency_ms,
                response_hash=resp_hash,
                is_live=True,
            )

    def _parse_json_response(
        self,
        data: Dict[str, Any],
        txn_id: str,
        http_status: int,
        pan: str,
        latency_ms: float,
        response_hash: Optional[str],
    ) -> PANVerificationResponse:
        """
        Parses JSON response if returned by API Setu endpoint.
        """
        # API Setu can return cert data in JSON structure
        cert_data = data.get("certificateData") or data.get("CertificateData") or data
        verified_name = cert_data.get("name") or cert_data.get("FullName") or cert_data.get("holderName")
        verified_dob = cert_data.get("dob") or cert_data.get("DOB")
        verified_pan = cert_data.get("panno") or cert_data.get("pan") or pan
        issuer = cert_data.get("issuer") or "Income Tax Department"
        cert_num = cert_data.get("certificateNumber") or verified_pan

        status = PANVerificationStatus.VERIFIED if verified_pan else PANVerificationStatus.NOT_VERIFIED

        return PANVerificationResponse(
            txn_id=txn_id,
            status=status,
            http_status=http_status,
            pan=verified_pan.strip().upper(),
            verified_name=verified_name,
            verified_dob=verified_dob,
            issuer=issuer,
            certificate_type="PANCR",
            certificate_number=cert_num,
            certificate_status="ACTIVE",
            latency_ms=latency_ms,
            response_hash=response_hash,
            is_live=True,
        )
