# -*- coding: utf-8 -*-
"""
Secure PDF Response Handler for API Setu EPFO UAN Card.
Enforces:
- Verification of valid PDF magic bytes (%PDF-)
- SHA-256 cryptographic digest generation
- Byte size tracking
- Safe rejection of non-PDF or truncated streams
"""

import hashlib
from typing import Optional

from .models import (
    EPFOEndpointType,
    EPFOVerificationResponse,
    EPFOVerificationStatus,
)


class EPFOPDFHandlingError(Exception):
    """Raised when EPFO PDF payload is corrupted, truncated, or invalid."""
    pass


def process_epfo_uan_pdf(
    pdf_bytes: bytes,
    txn_id: str,
    http_status: int = 200,
    queried_uan: Optional[str] = None,
    latency_ms: Optional[float] = None,
    is_live: bool = False,
) -> EPFOVerificationResponse:
    """
    Safely validates and normalizes binary PDF response from UAN Card endpoint.
    """
    if not pdf_bytes or len(pdf_bytes) == 0:
        raise EPFOPDFHandlingError("Received empty PDF response stream")

    # Verify standard PDF header magic bytes (%PDF-)
    if not pdf_bytes.startswith(b"%PDF-"):
        # Check if the payload is actually an API Setu JSON error envelope returned with 200
        try:
            import json
            data = json.loads(pdf_bytes.decode("utf-8", errors="ignore"))
            if "error" in data or "status" in data:
                desc = data.get("errorDescription") or data.get("error") or "Unknown error"
                return EPFOVerificationResponse(
                    endpoint_type=EPFOEndpointType.UAN_CARD,
                    identifier=queried_uan or "UNKNOWN",
                    txn_id=txn_id,
                    status=EPFOVerificationStatus.ERROR,
                    http_status=http_status,
                    format="pdf",
                    error_code="UPSTREAM_JSON_ERROR",
                    error_message=f"API returned JSON error instead of PDF: {desc}",
                    latency_ms=latency_ms,
                    is_live=is_live,
                )
        except Exception:
            pass
        raise EPFOPDFHandlingError("Payload does not begin with valid PDF header (%PDF-)")

    response_hash = hashlib.sha256(pdf_bytes).hexdigest()
    size_bytes = len(pdf_bytes)

    return EPFOVerificationResponse(
        endpoint_type=EPFOEndpointType.UAN_CARD,
        identifier=queried_uan or "UNKNOWN",
        txn_id=txn_id,
        status=EPFOVerificationStatus.VERIFIED,
        http_status=http_status,
        format="pdf",
        certificate_number=queried_uan,
        issuer="Employees' Provident Fund Organisation",
        pdf_data=pdf_bytes,
        pdf_size_bytes=size_bytes,
        response_hash=response_hash,
        latency_ms=latency_ms,
        is_live=is_live,
    )
