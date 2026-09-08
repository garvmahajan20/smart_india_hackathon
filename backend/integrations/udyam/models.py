# -*- coding: utf-8 -*-
"""
API Setu / MSME Udyam Verification Data Models.
Provides strongly typed models for requests, responses, status enums,
and validation logic strictly conforming to official API Setu specifications.
"""

import datetime
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# Official Udyam Registration Number format:
# UDYAM-XX-00-0000000 (e.g. UDYAM-MH-01-0088776 or UDYAM-DL-01-1234567)
UDYAM_REGEX = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$", re.IGNORECASE)


def is_valid_udyam_format(udyam: Optional[str]) -> bool:
    """
    Validates syntax format of an Udyam Registration Number.
    Note: Syntax validity is purely input validation; it is NOT verification.
    """
    if not udyam or not isinstance(udyam, str):
        return False
    return bool(UDYAM_REGEX.match(udyam.strip()))


class UdyamVerificationStatus(str, Enum):
    """
    Normalized Udyam verification status outcomes.
    Distinct from tender compliance PASS/FAIL verdicts.
    """
    VERIFIED = "VERIFIED"                  # Authoritative external registry confirmed record
    NOT_VERIFIED = "NOT_VERIFIED"          # External registry record not found or data mismatch
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"# Valid Udyam registered to a different enterprise
    INVALID_REQUEST = "INVALID_REQUEST"    # Malformed Udyam input or missing parameters
    ERROR = "ERROR"                        # Upstream gateway error (5xx, unexpected failure)
    UNAVAILABLE = "UNAVAILABLE"            # Timeout or network unreachable


@dataclass
class UdyamVerificationRequest:
    """
    Internal request model for official API Setu Udyam Certificate endpoint.
    POST /certificate/v3/msme/udcer
    Mandatory certificateParameters:
      - udyamNumber: exact casing per API spec
      - mobileNumber: linked mobile number
    """
    udyam_number: str
    mobile_number: str = "9874563210"      # Default sandbox test mobile
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def clean_udyam(self) -> str:
        return self.udyam_number.strip().upper() if self.udyam_number else ""

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Builds JSON payload required by official API Setu Udyam endpoint.
        Preserves exact field name 'udyamNumber' (NOT udyanNumber).
        """
        clean_u = self.clean_udyam()
        cert_params: Dict[str, str] = {
            "udyamNumber": clean_u,
            "mobileNumber": str(self.mobile_number).strip(),
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
                    "dataProvider": {"id": "in.gov.msme"},
                    "purpose": {"description": "GeM Bid Compliance MSME Verification"},
                    "user": {
                        "idType": "UDYAM",
                        "idNumber": clean_u,
                        "mobile": str(self.mobile_number).strip(),
                        "email": "test@email.com",
                    },
                    "data": {"id": "in.gov.msme"},
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
class UdyamVerificationResponse:
    """
    Normalized response structure for Udyam verification transactions.
    Preserves exact external fields without fabricating missing ones.
    """
    txn_id: str
    status: UdyamVerificationStatus
    http_status: int
    udyam_number: str
    enterprise_name: Optional[str] = None
    enterprise_type: Optional[str] = None  # Micro, Small, Medium
    major_activity: Optional[str] = None   # Manufacturing, Services
    date_of_commencement: Optional[str] = None
    social_category: Optional[str] = None  # General, SC, ST, OBC
    state: Optional[str] = None
    district: Optional[str] = None
    issuer: Optional[str] = None
    certificate_type: Optional[str] = None
    certificate_number: Optional[str] = None
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
            "udyam_number": self.udyam_number,
            "enterprise_name": self.enterprise_name,
            "enterprise_type": self.enterprise_type,
            "major_activity": self.major_activity,
            "date_of_commencement": self.date_of_commencement,
            "social_category": self.social_category,
            "state": self.state,
            "district": self.district,
            "issuer": self.issuer,
            "certificate_type": self.certificate_type,
            "certificate_number": self.certificate_number,
            "raw_response": self.raw_response,
            "response_hash": self.response_hash,
            "xml_field_paths": self.xml_field_paths,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "is_live": self.is_live,
        }
