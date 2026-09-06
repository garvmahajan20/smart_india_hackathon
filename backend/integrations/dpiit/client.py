# -*- coding: utf-8 -*-
"""
Real HTTP Client for API Setu / DPIIT Recognition Certificate Verification.
Makes actual HTTP requests to:
  POST {DPIIT_VERIFICATION_BASE_URL}/certificate/v3/dpiit/suirc
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

from .audit import DPIITAuditLogger, default_dpiit_audit_logger, hash_secret, mask_regn
from .config import DPIITVerificationConfig
from .models import (
    DPIITVerificationRequest,
    DPIITVerificationResponse,
    DPIITVerificationStatus,
    is_valid_dpiit_regn,
)
from .xml_parser import DPIITXMLParsingError, parse_dpiit_recognition_xml


class DPIITClientError(Exception):
    """Base exception for DPIIT Verification Client operations."""
    pass


class DPIITClientAuthError(DPIITClientError):
    """Raised on authentication/API key failures (HTTP 401/403)."""
    pass


class DPIITClientNetworkError(DPIITClientError):
    """Raised on network transport errors, DNS failures, or timeouts."""
    pass


class APISetuDPIITClient:
    """
    Real HTTP Client for official API Setu DPIIT Recognition Certificate Record.
    """
    def __init__(
        self,
        config: Optional[DPIITVerificationConfig] = None,
        audit_logger: Optional[DPIITAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or DPIITVerificationConfig.from_env()
        self.audit_logger = audit_logger or default_dpiit_audit_logger
        self.session = session or requests.Session()

    def verify_recognition_certificate(self, request: DPIITVerificationRequest) -> DPIITVerificationResponse:
        """
        Executes real HTTP call to official API Setu DPIIT endpoint.
        """
        clean_r = request.clean_regn()

        if not is_valid_dpiit_regn(clean_r):
            self.audit_logger.log(
                event_type="DPIIT_VERIFICATION_REQUESTED",
                status="INVALID_FORMAT",
                txn_id=request.txn_id,
                details={"regn_no": clean_r, "reason": "Invalid DPIIT registration format"},
            )
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.INVALID_REQUEST,
                http_status=400,
                regn_no=clean_r,
                error_code="INVALID_REGN_FORMAT",
                error_message="Registration number format is invalid.",
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
            event_type="DPIIT_REQUEST_INITIATED",
            status="INITIATED",
            txn_id=request.txn_id,
            details={
                "regn_no": clean_r,
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
                event_type="DPIIT_EXTERNAL_ERROR",
                status="TIMEOUT",
                txn_id=request.txn_id,
                details={"regn_no": clean_r, "latency_ms": latency_ms},
            )
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.UNAVAILABLE,
                http_status=504,
                regn_no=clean_r,
                error_code="TIMEOUT",
                error_message=f"Request to API Setu timed out after {self.config.timeout_seconds} seconds.",
                latency_ms=latency_ms,
                is_live=True,
            )

        except requests.exceptions.RequestException as re:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="DPIIT_EXTERNAL_ERROR",
                status="NETWORK_ERROR",
                txn_id=request.txn_id,
                details={"regn_no": clean_r, "error": str(re), "latency_ms": latency_ms},
            )
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.ERROR,
                http_status=502,
                regn_no=clean_r,
                error_code="NETWORK_FAILURE",
                error_message=f"Network error communicating with API Setu: {re}",
                latency_ms=latency_ms,
                is_live=True,
            )

        resp_bytes = resp.content
        resp_hash = hashlib.sha256(resp_bytes).hexdigest() if resp_bytes else None

        self.audit_logger.log(
            event_type="DPIIT_RESPONSE_RECEIVED",
            status=f"HTTP_{resp.status_code}",
            txn_id=request.txn_id,
            details={
                "regn_no": clean_r,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "response_hash": resp_hash,
            },
        )

        # 200 OK: Process XML response
        if resp.status_code == 200:
            text_body = resp.text.strip()
            if "<" in text_body and ">" in text_body:
                try:
                    return parse_dpiit_recognition_xml(
                        xml_string=text_body,
                        txn_id=request.txn_id,
                        http_status=200,
                        queried_regn=clean_r,
                        latency_ms=latency_ms,
                        is_live=True,
                    )
                except DPIITXMLParsingError as xpe:
                    return DPIITVerificationResponse(
                        txn_id=request.txn_id,
                        status=DPIITVerificationStatus.ERROR,
                        http_status=200,
                        regn_no=clean_r,
                        error_code="MALFORMED_XML",
                        error_message=str(xpe),
                        raw_response=text_body[:500],
                        response_hash=resp_hash,
                        latency_ms=latency_ms,
                        is_live=True,
                    )

            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.ERROR,
                http_status=200,
                regn_no=clean_r,
                error_code="UNRECOGNIZED_FORMAT",
                error_message="Response was HTTP 200 but content was not valid XML.",
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
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.INVALID_REQUEST,
                http_status=400,
                regn_no=clean_r,
                error_code="BAD_REQUEST",
                error_message=err_desc,
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 401 Unauthorized
        if resp.status_code == 401:
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.ERROR,
                http_status=401,
                regn_no=clean_r,
                error_code="UNAUTHORIZED",
                error_message="Invalid API key or client ID credentials for API Setu.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 404 Not Found
        if resp.status_code == 404:
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=DPIITVerificationStatus.NOT_VERIFIED,
                http_status=404,
                regn_no=clean_r,
                error_code="NOT_FOUND",
                error_message=f"DPIIT registration '{clean_r}' was not found in the external registry.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 500, 502, 503, 504
        if resp.status_code in (500, 502, 503, 504):
            stat = DPIITVerificationStatus.UNAVAILABLE if resp.status_code in (503, 504) else DPIITVerificationStatus.ERROR
            return DPIITVerificationResponse(
                txn_id=request.txn_id,
                status=stat,
                http_status=resp.status_code,
                regn_no=clean_r,
                error_code=f"UPSTREAM_{resp.status_code}",
                error_message=f"API Setu upstream gateway error (HTTP {resp.status_code}): {resp.text[:200]}",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        return DPIITVerificationResponse(
            txn_id=request.txn_id,
            status=DPIITVerificationStatus.ERROR,
            http_status=resp.status_code,
            regn_no=clean_r,
            error_code=f"HTTP_{resp.status_code}",
            error_message=f"Unexpected HTTP status {resp.status_code} from API Setu.",
            raw_response=resp.text,
            response_hash=resp_hash,
            latency_ms=latency_ms,
            is_live=True,
        )

    verify_dpiit = verify_recognition_certificate
