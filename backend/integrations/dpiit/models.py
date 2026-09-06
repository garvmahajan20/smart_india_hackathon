# -*- coding: utf-8 -*-
"""
API Setu / DPIIT Recognition Certificate Data Models.
Provides strongly typed models for requests, responses, status enums,
and validation logic strictly conforming to official API Setu specifications.
"""

import datetime
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# Official DPIIT / DIPP Registration number pattern (e.g. DIPP12345 or DIPPXXXX)
DPIIT_REGN_REGEX = re.compile(r"^(DIPP|DPIIT)?[0-9A-Z]{4,25}$", re.IGNORECASE)


def is_valid_dpiit_regn(regn: Optional[str]) -> bool:
    """Validates syntax format of a DPIIT Registration Number."""
    if not regn or not isinstance(regn, str):
        return False
    return bool(DPIIT_REGN_REGEX.match(regn.strip()))


def is_valid_mobile_format(mobile: Optional[str]) -> bool:
    """Validates 10-digit mobile number."""
    if not mobile or not isinstance(mobile, str):
        return False
    return bool(re.match(r"^[0-9]{10}$", mobile.strip()))


class DPIITVerificationStatus(str, Enum):
    """
    Normalized DPIIT verification status outcomes.
    Distinct from tender compliance PASS/FAIL verdicts.
    """
    VERIFIED = "VERIFIED"                  # Authoritative external registry confirmed record
    NOT_VERIFIED = "NOT_VERIFIED"          # External registry record not found or data mismatch
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"# Valid certificate registered to a different company
    INVALID_REQUEST = "INVALID_REQUEST"    # Malformed parameter or missing fields
    ERROR = "ERROR"                        # Upstream gateway error (5xx, unexpected failure)
    UNAVAILABLE = "UNAVAILABLE"            # Timeout or network unreachable


@dataclass
class DPIITVerificationRequest:
    """
    Internal request model for official API Setu DPIIT Recognition Certificate endpoint.
    POST /certificate/v3/dpiit/suirc
    CRITICAL: Preserves exact field names 'REGN_NO' and 'MobileNumber'.
    """
    regn_no: str
    mobile_number: str = "9807654321"      # Default sandbox test mobile
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def clean_regn(self) -> str:
        return self.regn_no.strip().upper() if self.regn_no else ""

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Builds JSON payload required by official API Setu DPIIT endpoint.
        Preserves EXACT field casing: REGN_NO, MobileNumber.
        """
        clean_r = self.clean_regn()
        cert_params: Dict[str, str] = {
            "REGN_NO": clean_r,
            "MobileNumber": str(self.mobile_number).strip(),
        }

        payload: Dict[str, Any] = {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": cert_params,
        }

        if self.consent_artifact:
            payload["consentArtifact"] = self.consent_artifact
        else:
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            payload["consentArtifact"] = {
                "consent": {
                    "consentId": str(uuid.uuid4()),
                    "timestamp": now_iso,
                    "dataConsumer": {"id": "in.gov.sandbox"},
                    "dataProvider": {"id": "in.gov.dpiit"},
                    "purpose": {"description": "GeM Bid Compliance Startup India Verification"},
                    "user": {
                        "idType": "DPIIT",
                        "idNumber": clean_r,
                        "mobile": str(self.mobile_number).strip(),
                        "email": "test@email.com",
                    },
                    "data": {"id": "in.gov.dpiit"},
                    "permission": {
                        "access": "VIEW",
                        "dateRange": {"from": now_iso, "to": now_iso},
                        "frequency": {"unit": "ONETIME", "value": 1, "repeats": 0},
                    },
                },
                "signature": {"signature": "SHA256withRSA_SIGNED_CONSENT"},
            }

        return payload


@dataclass
class DPIITVerificationResponse:
    """
    Normalized response structure for DPIIT verification transactions.
    Preserves exact external fields without fabricating missing ones.
    """
    txn_id: str
    status: DPIITVerificationStatus
    http_status: int
    regn_no: str
    startup_name: Optional[str] = None
    entity_type: Optional[str] = None      # Private Limited, LLP, Partnership
    incorporation_date: Optional[str] = None
    recognition_number: Optional[str] = None
    recognition_date: Optional[str] = None
    valid_upto: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    state: Optional[str] = None
    issuer: Optional[str] = "Department for Promotion of Industry and Internal Trade"
    certificate_type: Optional[str] = None
    raw_response: Optional[str] = None
    response_hash: Optional[str] = None
    xml_field_paths: Dict[str, str] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    is_live: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "status": self.status.value,
            "http_status": self.http_status,
            "regn_no": self.regn_no,
            "startup_name": self.startup_name,
            "entity_type": self.entity_type,
            "incorporation_date": self.incorporation_date,
            "recognition_number": self.recognition_number,
            "recognition_date": self.recognition_date,
            "valid_upto": self.valid_upto,
            "industry": self.industry,
            "sector": self.sector,
            "state": self.state,
            "issuer": self.issuer,
            "certificate_type": self.certificate_type,
            "raw_response": self.raw_response[:200] if self.raw_response else None,
            "response_hash": self.response_hash,
            "xml_field_paths": self.xml_field_paths,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "is_live": self.is_live,
        }
