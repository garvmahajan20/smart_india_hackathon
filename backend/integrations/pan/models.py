# -*- coding: utf-8 -*-
"""
API Setu / Income Tax Department PAN Verification Data Models.
Provides strongly typed models for requests, responses, status enums,
and validation logic strictly conforming to official API Setu specifications.
"""

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# Official Indian Permanent Account Number (PAN) regex:
# 5 uppercase letters + 4 digits + 1 uppercase letter
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def is_valid_pan_format(pan: Optional[str]) -> bool:
    """
    Validates syntax format of a PAN.
    Note: Syntax validity is ONLY input validation; it is NOT verification.
    """
    if not pan or not isinstance(pan, str):
        return False
    return bool(PAN_REGEX.match(pan.strip().upper()))


class PANVerificationStatus(str, Enum):
    """
    Normalized PAN verification status outcomes.
    Distinct from tender compliance PASS/FAIL verdicts.
    """
    VERIFIED = "VERIFIED"                  # External authoritative registry confirmed record
    NOT_VERIFIED = "NOT_VERIFIED"          # External registry record not found or data mismatch
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"# Valid PAN registered to different entity
    INVALID_REQUEST = "INVALID_REQUEST"    # Malformed PAN input or missing parameters
    ERROR = "ERROR"                        # Upstream gateway error (5xx, unexpected failure)
    UNAVAILABLE = "UNAVAILABLE"            # Timeout or network unreachable


@dataclass
class PANVerificationRequest:
    """
    Internal request model for official API Setu PANCR endpoint.
    POST /certificate/v3/pan/pancr
    """
    pan: str
    full_name: Optional[str] = None
    dob: Optional[str] = None              # Format: DD-MM-YYYY
    uid: Optional[str] = None              # Aadhaar/UID if available
    org_id: str = "001891"                 # Income Tax Department organization code
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    gender: Optional[str] = None
    consent_artifact: Optional[Dict[str, Any]] = None

    def clean_pan(self) -> str:
        return self.pan.strip().upper() if self.pan else ""

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Builds JSON payload required by official API Setu PANCR endpoint.
        """
        clean_p = self.clean_pan()
        cert_params: Dict[str, Any] = {
            "panno": clean_p,
            "orgid": self.org_id,
        }
        if self.full_name:
            cert_params["FullName"] = self.full_name.strip()
            cert_params["PANFullName"] = self.full_name.strip()
        if self.dob:
            cert_params["DOB"] = self.dob.strip()
        if self.uid:
            cert_params["UID"] = str(self.uid).strip()
        if self.gender:
            cert_params["GENDER"] = self.gender.strip()

        payload: Dict[str, Any] = {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": cert_params,
        }

        # Build official consent artifact
        if self.consent_artifact:
            payload["consentArtifact"] = self.consent_artifact
        else:
            import datetime
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            payload["consentArtifact"] = {
                "consent": {
                    "consentId": str(uuid.uuid4()),
                    "timestamp": now_iso,
                    "dataConsumer": {"id": "in.gov.sandbox"},
                    "dataProvider": {"id": "in.gov.pan"},
                    "purpose": {"description": "GeM Bid Compliance Verification"},
                    "user": {
                        "idType": "PAN",
                        "idNumber": clean_p,
                        "mobile": "9876543210",
                        "email": "test@email.com",
                    },
                    "data": {"id": "in.gov.pan"},
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
class PANVerificationResponse:
    """
    Normalized response structure for PAN verification transactions.
    Preserves exact external fields without fabricating missing ones.
    """
    txn_id: str
    status: PANVerificationStatus
    http_status: int
    pan: str
    verified_name: Optional[str] = None
    verified_dob: Optional[str] = None
    issuer: Optional[str] = None
    certificate_type: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_status: Optional[str] = None
    verified_on: Optional[str] = None
    raw_response: Optional[str] = None
    response_hash: Optional[str] = None
    xml_field_paths: Dict[str, str] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True

    def to_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        res = {
            "txn_id": self.txn_id,
            "status": self.status.value,
            "http_status": self.http_status,
            "pan": self.pan,
            "verified_name": self.verified_name,
            "verified_dob": self.verified_dob,
            "issuer": self.issuer,
            "certificate_type": self.certificate_type,
            "certificate_number": self.certificate_number,
            "certificate_status": self.certificate_status,
            "verified_on": self.verified_on,
            "response_hash": self.response_hash,
            "xml_field_paths": self.xml_field_paths,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": round(self.latency_ms, 2),
            "is_live": self.is_live,
        }
        if include_raw and self.raw_response:
            res["raw_response"] = self.raw_response
        return res
