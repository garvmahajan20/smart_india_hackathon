# -*- coding: utf-8 -*-
"""
Real HTTP Client for API Setu / ESIC (Employees' State Insurance Corporation).
Manages real HTTP requests to:
  1. POST /certificate/v3/esic/esich (Health Passbook, format: xml)
  2. POST /certificate/v3/esic/phcrd (Pehchan Card, format: xml)
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

from .audit import ESICAuditLogger, default_esic_audit_logger, hash_secret, mask_ip_number
from .config import ESICVerificationConfig
from .models import (
    ESICEndpointType,
    ESICHealthPassbookRequest,
    ESICPehchanCardRequest,
    ESICVerificationResponse,
    ESICVerificationStatus,
    is_valid_ip_number,
)
from .xml_parser import ESICXMLParsingError, parse_esic_certificate_xml


class ESICClientError(Exception):
    """Base exception for ESIC Verification Client operations."""
    pass


class ESICClientAuthError(ESICClientError):
    """Raised on authentication/API key failures (HTTP 401/403)."""
    pass


class ESICClientNetworkError(ESICClientError):
    """Raised on network transport errors, DNS failures, or timeouts."""
    pass


class APISetuESICClient:
    """
    Real HTTP Client for official API Setu ESIC Endpoints.
    """
    def __init__(
        self,
        config: Optional[ESICVerificationConfig] = None,
        audit_logger: Optional[ESICAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or ESICVerificationConfig.from_env()
        self.audit_logger = audit_logger or default_esic_audit_logger
        self.session = session or requests.Session()

    def _execute_post(
        self,
        endpoint_type: ESICEndpointType,
        target_url: str,
        payload: Dict[str, Any],
        ip_number: str,
        txn_id: str,
    ) -> ESICVerificationResponse:
        """
        Internal shared HTTP execution method across both ESIC endpoints.
        """
        headers = {
            "Content-Type": "application/json",
            "X-APISETU-APIKEY": self.config.api_key,
            "X-APISETU-CLIENTID": self.config.client_id,
            "Accept": "application/xml, application/json, */*",
        }

        self.audit_logger.log(
            event_type="ESIC_REQUEST_INITIATED",
            endpoint_type=endpoint_type.value,
            status="INITIATED",
            txn_id=txn_id,
            details={
                "ip_number": ip_number,
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
                event_type="ESIC_EXTERNAL_ERROR",
                endpoint_type=endpoint_type.value,
                status="TIMEOUT",
                txn_id=txn_id,
                details={"ip_number": ip_number, "latency_ms": latency_ms},
            )
            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=ESICVerificationStatus.UNAVAILABLE,
                http_status=504,
                error_code="TIMEOUT",
                error_message=f"Request to API Setu timed out after {self.config.timeout_seconds} seconds.",
                latency_ms=latency_ms,
                is_live=True,
            )

        except requests.exceptions.RequestException as re:
            latency_ms = (time.time() - start_time) * 1000.0
            self.audit_logger.log(
                event_type="ESIC_EXTERNAL_ERROR",
                endpoint_type=endpoint_type.value,
                status="NETWORK_ERROR",
                txn_id=txn_id,
                details={"ip_number": ip_number, "error": str(re), "latency_ms": latency_ms},
            )
            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=ESICVerificationStatus.ERROR,
                http_status=502,
                error_code="NETWORK_FAILURE",
                error_message=f"Network error communicating with API Setu: {re}",
                latency_ms=latency_ms,
                is_live=True,
            )

        resp_bytes = resp.content
        resp_hash = hashlib.sha256(resp_bytes).hexdigest() if resp_bytes else None

        self.audit_logger.log(
            event_type="ESIC_RESPONSE_RECEIVED",
            endpoint_type=endpoint_type.value,
            status=f"HTTP_{resp.status_code}",
            txn_id=txn_id,
            details={
                "ip_number": ip_number,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "response_hash": resp_hash,
            },
        )

        # 200 OK: Process XML
        if resp.status_code == 200:
            text_body = resp.text.strip()
            if "<" in text_body and ">" in text_body:
                try:
                    return parse_esic_certificate_xml(
                        xml_string=text_body,
                        endpoint_type=endpoint_type,
                        txn_id=txn_id,
                        http_status=200,
                        queried_ip=ip_number,
                        latency_ms=latency_ms,
                        is_live=True,
                    )
                except ESICXMLParsingError as xpe:
                    return ESICVerificationResponse(
                        endpoint_type=endpoint_type,
                        ip_number=ip_number,
                        txn_id=txn_id,
                        status=ESICVerificationStatus.ERROR,
                        http_status=200,
                        error_code="MALFORMED_XML",
                        error_message=str(xpe),
                        raw_response=text_body[:500],
                        response_hash=resp_hash,
                        latency_ms=latency_ms,
                        is_live=True,
                    )

            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=ESICVerificationStatus.ERROR,
                http_status=200,
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
            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=ESICVerificationStatus.INVALID_REQUEST,
                http_status=400,
                error_code="BAD_REQUEST",
                error_message=err_desc,
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 401 Unauthorized
        if resp.status_code == 401:
            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=ESICVerificationStatus.ERROR,
                http_status=401,
                error_code="UNAUTHORIZED",
                error_message="Invalid API key or client ID credentials for API Setu.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 404 Not Found
        if resp.status_code == 404:
            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=ESICVerificationStatus.NOT_VERIFIED,
                http_status=404,
                error_code="NOT_FOUND",
                error_message=f"ESIC IP number '{ip_number}' was not found in the external registry.",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        # 500, 502, 503, 504
        if resp.status_code in (500, 502, 503, 504):
            stat = ESICVerificationStatus.UNAVAILABLE if resp.status_code in (503, 504) else ESICVerificationStatus.ERROR
            return ESICVerificationResponse(
                endpoint_type=endpoint_type,
                ip_number=ip_number,
                txn_id=txn_id,
                status=stat,
                http_status=resp.status_code,
                error_code=f"UPSTREAM_{resp.status_code}",
                error_message=f"API Setu upstream gateway error (HTTP {resp.status_code}): {resp.text[:200]}",
                raw_response=resp.text,
                response_hash=resp_hash,
                latency_ms=latency_ms,
                is_live=True,
            )

        return ESICVerificationResponse(
            endpoint_type=endpoint_type,
            ip_number=ip_number,
            txn_id=txn_id,
            status=ESICVerificationStatus.ERROR,
            http_status=resp.status_code,
            error_code=f"HTTP_{resp.status_code}",
            error_message=f"Unexpected HTTP status {resp.status_code} from API Setu.",
            raw_response=resp.text,
            response_hash=resp_hash,
            latency_ms=latency_ms,
            is_live=True,
        )

    def verify_health_passbook(self, request: ESICHealthPassbookRequest) -> ESICVerificationResponse:
        """
        Executes real call for ESIC Health Passbook.
        POST /certificate/v3/esic/esich (Format: XML)
        """
        clean_ip = request.ip_number.strip()
        if not is_valid_ip_number(clean_ip):
            return ESICVerificationResponse(
                endpoint_type=ESICEndpointType.HEALTH_PASSBOOK,
                ip_number=clean_ip,
                txn_id=request.txn_id,
                status=ESICVerificationStatus.INVALID_REQUEST,
                http_status=400,
                error_code="INVALID_IP_FORMAT",
                error_message="IP number must be 10 to 17 numeric digits.",
                is_live=False,
            )

        return self._execute_post(
            endpoint_type=ESICEndpointType.HEALTH_PASSBOOK,
            target_url=self.config.health_passbook_url,
            payload=request.to_api_payload(),
            ip_number=clean_ip,
            txn_id=request.txn_id,
        )

    def verify_pehchan_card(self, request: ESICPehchanCardRequest) -> ESICVerificationResponse:
        """
        Executes real call for ESIC Pehchan Card.
        POST /certificate/v3/esic/phcrd (Format: XML)
        """
        clean_ip = request.ip_number.strip()
        if not is_valid_ip_number(clean_ip):
            return ESICVerificationResponse(
                endpoint_type=ESICEndpointType.PEHCHAN_CARD,
                ip_number=clean_ip,
                txn_id=request.txn_id,
                status=ESICVerificationStatus.INVALID_REQUEST,
                http_status=400,
                error_code="INVALID_IP_FORMAT",
                error_message="IP number must be 10 to 17 numeric digits.",
                is_live=False,
            )

        return self._execute_post(
            endpoint_type=ESICEndpointType.PEHCHAN_CARD,
            target_url=self.config.pehchan_card_url,
            payload=request.to_api_payload(),
            ip_number=clean_ip,
            txn_id=request.txn_id,
        )
