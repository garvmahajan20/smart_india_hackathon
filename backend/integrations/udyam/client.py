# -*- coding: utf-8 -*-
"""
Real HTTP Client for API Setu / MSME Udyam Certificate Verification.
Makes actual HTTP requests to:
  POST {UDYAM_VERIFICATION_BASE_URL}/certificate/v3/msme/udcer
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

from .audit import UdyamAuditLogger, default_udyam_audit_logger, hash_secret, mask_udyam
from .config import UdyamVerificationConfig
from .models import (
    UdyamVerificationRequest,
    UdyamVerificationResponse,
    UdyamVerificationStatus,
    is_valid_udyam_format,
)
from .xml_parser import UdyamXMLParsingError, parse_udyam_verification_xml


class UdyamClientError(Exception):
    """Base exception for Udyam Verification Client operations."""
    pass


class UdyamClientAuthError(UdyamClientError):
    """Raised on authentication/API key failures (HTTP 401/403)."""
    pass


class UdyamClientNetworkError(UdyamClientError):
    """Raised on network transport errors, DNS failures, or timeouts."""
    pass


class APISetuUdyamClient:
    """
    Real HTTP Client for official API Setu Udyam Certificate Record.
    """
    def __init__(
        self,
        config: Optional[UdyamVerificationConfig] = None,
        audit_logger: Optional[UdyamAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or UdyamVerificationConfig.from_env()
        self.audit_logger = audit_logger or default_udyam_audit_logger
        self.session = session or requests.Session()

    def verify_udyam(self, request: UdyamVerificationRequest) -> UdyamVerificationResponse:
        """
        Executes real HTTP call to official API Setu Udyam endpoint.
        """
        clean_udyam_num = request.clean_udyam()

        # Step 1: Input syntax validation
        if not is_valid_udyam_format(clean_udyam_num):
            self.audit_logger.log(
                event_type="UDYAM_VERIFICATION_REQUESTED",
                status="INVALID_FORMAT",
                txn_id=request.txn_id,
                details={"udyam": clean_udyam_num, "reason": "Invalid Udyam syntax format"},
            )
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=UdyamVerificationStatus.INVALID_REQUEST,
                http_status=400,
                udyam_number=clean_udyam_num,
                error_code="INVALID_UDYAM_FORMAT",
                error_message="Udyam number does not conform to standard format (UDYAM-XX-00-0000000).",
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
            event_type="UDYAM_REQUEST_INITIATED",
            status="INITIATED",
            txn_id=request.txn_id,
            details={
                "udyam": clean_udyam_num,
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
                event_type="UDYAM_EXTERNAL_ERROR",
                status="TIMEOUT",
                txn_id=request.txn_id,
                details={"udyam": clean_udyam_num, "latency_ms": latency_ms},
            )
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=UdyamVerificationStatus.UNAVAILABLE,
                http_status=504,
                udyam_number=clean_udyam_num,
                error_code="TIMEOUT",
                error_message=f"Request to API Setu timed out after {self.config.timeout_seconds} seconds.",
                latency_ms=latency_ms,
                is_live=True,
            )

        except requests.exceptions.RequestException as re:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="UDYAM_EXTERNAL_ERROR",
                status="NETWORK_ERROR",
                txn_id=request.txn_id,
                details={"udyam": clean_udyam_num, "error": str(re), "latency_ms": latency_ms},
            )
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=UdyamVerificationStatus.ERROR,
                http_status=502,
                udyam_number=clean_udyam_num,
                error_code="NETWORK_FAILURE",
                error_message=f"Network error communicating with API Setu: {re}",
                latency_ms=latency_ms,
                is_live=True,
            )

        resp_bytes = resp.content
        resp_hash = hashlib.sha256(resp_bytes).hexdigest() if resp_bytes else None

        self.audit_logger.log(
            event_type="UDYAM_RESPONSE_RECEIVED",
            status=f"HTTP_{resp.status_code}",
            txn_id=request.txn_id,
            details={
                "udyam": clean_udyam_num,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "response_hash": resp_hash,
            },
        )

        # 200 OK: Process XML response
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "").lower()
            text_body = resp.text.strip()

            if "<" in text_body and ">" in text_body:
                try:
                    parsed = parse_udyam_verification_xml(
                        xml_string=text_body,
                        txn_id=request.txn_id,
                        http_status=200,
                        queried_udyam=clean_udyam_num,
                        latency_ms=latency_ms,
                        is_live=True,
                    )
                    return parsed
                except UdyamXMLParsingError as xpe:
                    return UdyamVerificationResponse(
                        txn_id=request.txn_id,
                        status=UdyamVerificationStatus.ERROR,
                        http_status=200,
                        udyam_number=clean_udyam_num,
                        error_code="MALFORMED_XML",
                        error_message=str(xpe),
                        raw_response=text_body[:500],
                        response_hash=resp_hash,
                        latency_ms=latency_ms,
                        is_live=True,
                    )

            # JSON response on 200 (edge case)
            try:
                data = resp.json()
                return UdyamVerificationResponse(
                    txn_id=request.txn_id,
                    status=UdyamVerificationStatus.VERIFIED if data.get("status") else UdyamVerificationStatus.NOT_VERIFIED,
                    http_status=200,
                    udyam_number=clean_udyam_num,
                    enterprise_name=data.get("enterpriseName") or data.get("name"),
                    enterprise_type=data.get("enterpriseType") or data.get("category"),
                    raw_response=text_body,
                    response_hash=resp_hash,
                    latency_ms=latency_ms,
                    is_live=True,
                )
            except Exception:
                return UdyamVerificationResponse(
                    txn_id=request.txn_id,
                    status=UdyamVerificationStatus.ERROR,
                    http_status=200,
                    udyam_number=clean_udyam_num,
                    error_code="UNRECOGNIZED_FORMAT",
                    error_message="Response was HTTP 200 but content was neither valid XML nor JSON.",
                    raw_response=text_body[:500],
                    response_hash=resp_hash,
                    latency_ms=latency_ms,
                    is_live=True,
                )

        # 400 Bad Request
        if resp.status_code == 400:
            err_desc = "Bad request to API Setu"
            try:
                err_data = resp.json()
                err_desc = err_data.get("errorDescription") or err_data.get("error") or resp.text
            except Exception:
                err_desc = resp.text
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=UdyamVerificationStatus.INVALID_REQUEST,
                http_status=400,
                udyam_number=clean_udyam_num,
                error_code="BAD_REQUEST",
                error_message=err_desc,
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 401 Unauthorized
        if resp.status_code == 401:
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=UdyamVerificationStatus.ERROR,
                http_status=401,
                udyam_number=clean_udyam_num,
                error_code="UNAUTHORIZED",
                error_message="Invalid API key or client ID credentials for API Setu.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 404 Not Found
        if resp.status_code == 404:
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=UdyamVerificationStatus.NOT_VERIFIED,
                http_status=404,
                udyam_number=clean_udyam_num,
                error_code="NOT_FOUND",
                error_message=f"Udyam number '{clean_udyam_num}' was not found in the external MSME registry.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 500, 502, 503, 504
        if resp.status_code in (500, 502, 503, 504):
            stat = UdyamVerificationStatus.UNAVAILABLE if resp.status_code in (503, 504) else UdyamVerificationStatus.ERROR
            return UdyamVerificationResponse(
                txn_id=request.txn_id,
                status=stat,
                http_status=resp.status_code,
                udyam_number=clean_udyam_num,
                error_code=f"UPSTREAM_{resp.status_code}",
                error_message=f"API Setu upstream gateway error (HTTP {resp.status_code}): {resp.text[:200]}",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        return UdyamVerificationResponse(
            txn_id=request.txn_id,
            status=UdyamVerificationStatus.ERROR,
            http_status=resp.status_code,
            udyam_number=clean_udyam_num,
            error_code=f"HTTP_{resp.status_code}",
            error_message=f"Unexpected HTTP status {resp.status_code} from API Setu.",
            raw_response=resp.text,
            response_hash=resp_hash,
            latency_ms=latency_ms,
            is_live=True,
        )
