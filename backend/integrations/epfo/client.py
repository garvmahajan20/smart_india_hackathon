# -*- coding: utf-8 -*-
"""
Real HTTP Client for API Setu / EPFO (Employees' Provident Fund Organisation).
Manages real HTTP requests to:
  1. POST /certificate/v3/epfindia/uncrd (UAN Card, format: pdf)
  2. POST /certificate/v3/epfindia/epfsc (Scheme Certificate, format: xml)
  3. POST /certificate/v3/epfindia/pecer (Pension Certificate, format: xml)
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

from .audit import EPFOAuditLogger, default_epfo_audit_logger, hash_secret, mask_identifier
from .config import EPFOVerificationConfig
from .models import (
    EPFOEndpointType,
    EPFOVerificationResponse,
    EPFOVerificationStatus,
    PensionCertificateRequest,
    SchemeCertificateRequest,
    UANCardRequest,
    is_valid_dob_format,
    is_valid_ppono_format,
    is_valid_scno_format,
    is_valid_uan_format,
)
from .pdf_handler import EPFOPDFHandlingError, process_epfo_uan_pdf
from .xml_parser import EPFOXMLParsingError, parse_epfo_certificate_xml


class EPFOClientError(Exception):
    """Base exception for EPFO Verification Client operations."""
    pass


class EPFOClientAuthError(EPFOClientError):
    """Raised on authentication/API key failures (HTTP 401/403)."""
    pass


class EPFOClientNetworkError(EPFOClientError):
    """Raised on network transport errors, DNS failures, or timeouts."""
    pass


class APISetuEPFOClient:
    """
    Real HTTP Client for official API Setu EPFO Endpoints.
    """
    def __init__(
        self,
        config: Optional[EPFOVerificationConfig] = None,
        audit_logger: Optional[EPFOAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or EPFOVerificationConfig.from_env()
        self.audit_logger = audit_logger or default_epfo_audit_logger
        self.session = session or requests.Session()

    def _execute_post(
        self,
        endpoint_type: EPFOEndpointType,
        target_url: str,
        payload: Dict[str, Any],
        identifier: str,
        expected_format: str,
        txn_id: str,
    ) -> EPFOVerificationResponse:
        """
        Internal shared HTTP execution method across all three EPFO endpoints.
        """
        headers = {
            "Content-Type": "application/json",
            "X-APISETU-APIKEY": self.config.api_key,
            "X-APISETU-CLIENTID": self.config.client_id,
            "Accept": "application/pdf, application/xml, application/json, */*",
        }

        self.audit_logger.log(
            event_type="EPFO_REQUEST_INITIATED",
            endpoint_type=endpoint_type.value,
            status="INITIATED",
            txn_id=txn_id,
            details={
                "identifier": identifier,
                "endpoint": target_url,
                "client_id": self.config.client_id,
                "api_key_hash": hash_secret(self.config.api_key),
            },
        )

        start_time = time.time()
        try:
            resp = self.session.post(
                target_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
                verify=True,  # Mandatory TLS validation
            )
            latency_ms = (time.time() - start_time) * 1000.0

        except requests.exceptions.Timeout as te:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="EPFO_EXTERNAL_ERROR",
                endpoint_type=endpoint_type.value,
                status="TIMEOUT",
                txn_id=txn_id,
                details={"identifier": identifier, "latency_ms": latency_ms},
            )
            return EPFOVerificationResponse(
                endpoint_type=endpoint_type,
                identifier=identifier,
                txn_id=txn_id,
                status=EPFOVerificationStatus.UNAVAILABLE,
                http_status=504,
                format=expected_format,
                error_code="TIMEOUT",
                error_message=f"Request to API Setu timed out after {self.config.timeout_seconds} seconds.",
                latency_ms=latency_ms,
                is_live=True,
            )

        except requests.exceptions.RequestException as re:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="EPFO_EXTERNAL_ERROR",
                endpoint_type=endpoint_type.value,
                status="NETWORK_ERROR",
                txn_id=txn_id,
                details={"identifier": identifier, "error": str(re), "latency_ms": latency_ms},
            )
            return EPFOVerificationResponse(
                endpoint_type=endpoint_type,
                identifier=identifier,
                txn_id=txn_id,
                status=EPFOVerificationStatus.ERROR,
                http_status=502,
                format=expected_format,
                error_code="NETWORK_FAILURE",
                error_message=f"Network error communicating with API Setu: {re}",
                latency_ms=latency_ms,
                is_live=True,
            )

        resp_bytes = resp.content
        resp_hash = hashlib.sha256(resp_bytes).hexdigest() if resp_bytes else None

        self.audit_logger.log(
            event_type="EPFO_RESPONSE_RECEIVED",
            endpoint_type=endpoint_type.value,
            status=f"HTTP_{resp.status_code}",
            txn_id=txn_id,
            details={
                "identifier": identifier,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "response_hash": resp_hash,
            },
        )

        # 200 OK: Process based on expected format
        if resp.status_code == 200:
            if expected_format == "pdf":
                try:
                    return process_epfo_uan_pdf(
                        pdf_bytes=resp_bytes,
                        txn_id=txn_id,
                        http_status=200,
                        queried_uan=identifier,
                        latency_ms=latency_ms,
                        is_live=True,
                    )
                except EPFOPDFHandlingError as phe:
                    return EPFOVerificationResponse(
                        endpoint_type=endpoint_type,
                        identifier=identifier,
                        txn_id=txn_id,
                        status=EPFOVerificationStatus.ERROR,
                        http_status=200,
                        format="pdf",
                        error_code="INVALID_PDF",
                        error_message=str(phe),
                        response_hash=resp_hash,
                        latency_ms=latency_ms,
                        is_live=True,
                    )
            else:
                # XML expected
                text_body = resp.text.strip()
                try:
                    return parse_epfo_certificate_xml(
                        xml_string=text_body,
                        endpoint_type=endpoint_type,
                        txn_id=txn_id,
                        http_status=200,
                        queried_identifier=identifier,
                        latency_ms=latency_ms,
                        is_live=True,
                    )
                except EPFOXMLParsingError as xpe:
                    return EPFOVerificationResponse(
                        endpoint_type=endpoint_type,
                        identifier=identifier,
                        txn_id=txn_id,
                        status=EPFOVerificationStatus.ERROR,
                        http_status=200,
                        format="xml",
                        error_code="MALFORMED_XML",
                        error_message=str(xpe),
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
            return EPFOVerificationResponse(
                endpoint_type=endpoint_type,
                identifier=identifier,
                txn_id=txn_id,
                status=EPFOVerificationStatus.INVALID_REQUEST,
                http_status=400,
                format=expected_format,
                error_code="BAD_REQUEST",
                error_message=err_desc,
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 401 Unauthorized
        if resp.status_code == 401:
            return EPFOVerificationResponse(
                endpoint_type=endpoint_type,
                identifier=identifier,
                txn_id=txn_id,
                status=EPFOVerificationStatus.ERROR,
                http_status=401,
                format=expected_format,
                error_code="UNAUTHORIZED",
                error_message="Invalid API key or client ID credentials for API Setu.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 404 Not Found
        if resp.status_code == 404:
            return EPFOVerificationResponse(
                endpoint_type=endpoint_type,
                identifier=identifier,
                txn_id=txn_id,
                status=EPFOVerificationStatus.NOT_VERIFIED,
                http_status=404,
                format=expected_format,
                error_code="NOT_FOUND",
                error_message=f"EPFO identifier '{identifier}' was not found in the external registry.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 500, 502, 503, 504
        if resp.status_code in (500, 502, 503, 504):
            stat = EPFOVerificationStatus.UNAVAILABLE if resp.status_code in (503, 504) else EPFOVerificationStatus.ERROR
            return EPFOVerificationResponse(
                endpoint_type=endpoint_type,
                identifier=identifier,
                txn_id=txn_id,
                status=stat,
                http_status=resp.status_code,
                format=expected_format,
                error_code=f"UPSTREAM_{resp.status_code}",
                error_message=f"API Setu upstream gateway error (HTTP {resp.status_code}): {resp.text[:200]}",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        return EPFOVerificationResponse(
            endpoint_type=endpoint_type,
            identifier=identifier,
            txn_id=txn_id,
            status=EPFOVerificationStatus.ERROR,
            http_status=resp.status_code,
            format=expected_format,
            error_code=f"HTTP_{resp.status_code}",
            error_message=f"Unexpected HTTP status {resp.status_code} from API Setu.",
            raw_response=resp.text,
            response_hash=resp_hash,
            latency_ms=latency_ms,
            is_live=True,
        )

    def verify_uan_card(self, request: UANCardRequest) -> EPFOVerificationResponse:
        """
        Executes real call for EPFO UAN Card.
        POST /certificate/v3/epfindia/uncrd (Format: PDF)
        """
        clean_uan = request.uan.strip()
        if not is_valid_uan_format(clean_uan):
            return EPFOVerificationResponse(
                endpoint_type=EPFOEndpointType.UAN_CARD,
                identifier=clean_uan,
                txn_id=request.txn_id,
                status=EPFOVerificationStatus.INVALID_REQUEST,
                http_status=400,
                format="pdf",
                error_code="INVALID_UAN_FORMAT",
                error_message="UAN must be a 10 to 12 digit number.",
                is_live=False,
            )
        if not is_valid_dob_format(request.dob):
            return EPFOVerificationResponse(
                endpoint_type=EPFOEndpointType.UAN_CARD,
                identifier=clean_uan,
                txn_id=request.txn_id,
                status=EPFOVerificationStatus.INVALID_REQUEST,
                http_status=400,
                format="pdf",
                error_code="INVALID_DOB_FORMAT",
                error_message="DOB must be in DD-MM-YYYY format.",
                is_live=False,
            )

        return self._execute_post(
            endpoint_type=EPFOEndpointType.UAN_CARD,
            target_url=self.config.uan_card_url,
            payload=request.to_api_payload(),
            identifier=clean_uan,
            expected_format="pdf",
            txn_id=request.txn_id,
        )

    def verify_scheme_certificate(self, request: SchemeCertificateRequest) -> EPFOVerificationResponse:
        """
        Executes real call for EPFO Scheme Certificate.
        POST /certificate/v3/epfindia/epfsc (Format: XML)
        """
        clean_scno = request.scno.strip().upper()
        if not is_valid_scno_format(clean_scno):
            return EPFOVerificationResponse(
                endpoint_type=EPFOEndpointType.SCHEME_CERTIFICATE,
                identifier=clean_scno,
                txn_id=request.txn_id,
                status=EPFOVerificationStatus.INVALID_REQUEST,
                http_status=400,
                format="xml",
                error_code="INVALID_SCNO_FORMAT",
                error_message="Scheme Certificate Number must be alphanumeric (5-30 chars).",
                is_live=False,
            )

        return self._execute_post(
            endpoint_type=EPFOEndpointType.SCHEME_CERTIFICATE,
            target_url=self.config.scheme_cert_url,
            payload=request.to_api_payload(),
            identifier=clean_scno,
            expected_format="xml",
            txn_id=request.txn_id,
        )

    def verify_pension_certificate(self, request: PensionCertificateRequest) -> EPFOVerificationResponse:
        """
        Executes real call for EPFO Pension Certificate.
        POST /certificate/v3/epfindia/pecer (Format: XML)
        """
        clean_ppono = request.ppono.strip().upper()
        if not is_valid_ppono_format(clean_ppono):
            return EPFOVerificationResponse(
                endpoint_type=EPFOEndpointType.PENSION_CERTIFICATE,
                identifier=clean_ppono,
                txn_id=request.txn_id,
                status=EPFOVerificationStatus.INVALID_REQUEST,
                http_status=400,
                format="xml",
                error_code="INVALID_PPONO_FORMAT",
                error_message="PPO Number must be alphanumeric (5-30 chars).",
                is_live=False,
            )

        return self._execute_post(
            endpoint_type=EPFOEndpointType.PENSION_CERTIFICATE,
            target_url=self.config.pension_cert_url,
            payload=request.to_api_payload(),
            identifier=clean_ppono,
            expected_format="xml",
            txn_id=request.txn_id,
        )
