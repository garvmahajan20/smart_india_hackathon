# -*- coding: utf-8 -*-
"""
API Setu / EPFO Verification Data Models.
Provides strongly typed models for requests, responses, status enums,
and validation logic strictly conforming to official API Setu specifications.

CRITICAL SCOPE DISTINCTION:
These models represent EPFO DOCUMENT/CERTIFICATE VERIFICATION ONLY.
They do NOT perform general employer EPFO compliance verification.
"""

import datetime
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EPFOEndpointType(str, Enum):
    UAN_CARD = "UAN_CARD"                       # Format: PDF
    SCHEME_CERTIFICATE = "SCHEME_CERTIFICATE"   # Format: XML
    PENSION_CERTIFICATE = "PENSION_CERTIFICATE" # Format: XML


class EPFOVerificationStatus(str, Enum):
    """
    Normalized EPFO verification status outcomes.
    Distinct from tender compliance PASS/FAIL verdicts.
    """
    VERIFIED = "VERIFIED"                  # Authoritative external registry confirmed record
    NOT_VERIFIED = "NOT_VERIFIED"          # External registry record not found or data mismatch
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"# Valid certificate registered to different person/entity
    INVALID_REQUEST = "INVALID_REQUEST"    # Malformed parameter or syntax error
    ERROR = "ERROR"                        # Upstream gateway error (5xx, unexpected failure)
    UNAVAILABLE = "UNAVAILABLE"            # Timeout or network unreachable


def is_valid_uan_format(uan: Optional[str]) -> bool:
    """UAN is typically a 10 to 12 digit numeric identifier."""
    if not uan or not isinstance(uan, str):
        return False
    return bool(re.match(r"^[0-9]{10,12}$", uan.strip()))


def is_valid_dob_format(dob: Optional[str]) -> bool:
    """DOB must be in DD-MM-YYYY format."""
    if not dob or not isinstance(dob, str):
        return False
    return bool(re.match(r"^[0-9]{2}-[0-9]{2}-[0-9]{4}$", dob.strip()))


def is_valid_scno_format(scno: Optional[str]) -> bool:
    """Scheme Certificate Number (alphanumeric, typically 8-20 chars)."""
    if not scno or not isinstance(scno, str):
        return False
    return bool(re.match(r"^[A-Z0-9]{5,30}$", scno.strip().upper()))


def is_valid_ppono_format(ppono: Optional[str]) -> bool:
    """Pension Payment Order Number (alphanumeric, typically 8-30 chars)."""
    if not ppono or not isinstance(ppono, str):
        return False
    return bool(re.match(r"^[A-Z0-9]{5,30}$", ppono.strip().upper()))


def build_epfo_consent_artifact(
    id_type: str,
    id_number: str,
    mobile: str = "9988776655",
    email: str = "test@email.com",
) -> Dict[str, Any]:
    """Builds standard consentArtifact structure for EPFO endpoints."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "consent": {
            "consentId": str(uuid.uuid4()),
            "timestamp": now_iso,
            "dataConsumer": {"id": "in.gov.sandbox"},
            "dataProvider": {"id": "in.gov.epfindia"},
            "purpose": {"description": "GeM Bidder EPFO Document Verification"},
            "user": {
                "idType": id_type,
                "idNumber": str(id_number).strip(),
                "mobile": mobile,
                "email": email,
            },
            "data": {"id": "in.gov.epfindia"},
            "permission": {
                "access": "VIEW",
                "dateRange": {"from": now_iso, "to": now_iso},
                "frequency": {"unit": "ONETIME", "value": 1, "repeats": 0},
            },
        },
        "signature": {"signature": "SHA256withRSA_SIGNED_CONSENT"},
    }


@dataclass
class UANCardRequest:
    """
    Request model for EPFO UAN Card endpoint.
    POST /certificate/v3/epfindia/uncrd
    Official format: pdf
    """
    uan: str
    dob: str                              # Format: DD-MM-YYYY (e.g. 31-12-1980)
    format: str = "pdf"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def to_api_payload(self) -> Dict[str, Any]:
        clean_uan = self.uan.strip()
        clean_dob = self.dob.strip()
        consent = self.consent_artifact or build_epfo_consent_artifact("UAN", clean_uan)
        return {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": {
                "UAN": clean_uan,
                "DOB": clean_dob,
            },
            "consentArtifact": consent,
        }


@dataclass
class SchemeCertificateRequest:
    """
    Request model for EPFO Scheme Certificate endpoint.
    POST /certificate/v3/epfindia/epfsc
    Official format: xml
    """
    scno: str                             # Scheme Certificate Number (e.g. APSID00040466)
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def to_api_payload(self) -> Dict[str, Any]:
        clean_scno = self.scno.strip().upper()
        consent = self.consent_artifact or build_epfo_consent_artifact("SCNO", clean_scno)
        return {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": {
                "SCNO": clean_scno,
            },
            "consentArtifact": consent,
        }


@dataclass
class PensionCertificateRequest:
    """
    Request model for EPFO Pension Certificate endpoint.
    POST /certificate/v3/epfindia/pecer
    Official format: xml
    """
    ppono: str                            # Pension Payment Order Number (e.g. DLCPM00052882)
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def to_api_payload(self) -> Dict[str, Any]:
        clean_ppono = self.ppono.strip().upper()
        consent = self.consent_artifact or build_epfo_consent_artifact("PPONO", clean_ppono)
        return {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": {
                "PPONO": clean_ppono,
            },
            "consentArtifact": consent,
        }


@dataclass
class EPFOVerificationResponse:
    """
    Unified normalized response structure for all EPFO verification transactions.
    Preserves exact external fields without fabricating missing ones.
    """
    endpoint_type: EPFOEndpointType
    identifier: str                       # UAN, SCNO, or PPONO
    txn_id: str
    status: EPFOVerificationStatus
    http_status: int
    format: str                           # "pdf" or "xml"
    member_name: Optional[str] = None
    dob: Optional[str] = None
    father_husband_name: Optional[str] = None
    certificate_number: Optional[str] = None
    issue_date: Optional[str] = None
    issuer: Optional[str] = "Employees' Provident Fund Organisation"
    pdf_data: Optional[bytes] = None
    pdf_size_bytes: Optional[int] = None
    raw_response: Optional[str] = None
    response_hash: Optional[str] = None
    xml_field_paths: Dict[str, str] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    is_live: bool = False

    # Non-negotiable scope limitation metadata
    is_employer_compliance: bool = False
    scope_notice: str = "EPFO_DOCUMENT_CERTIFICATE_VERIFICATION_ONLY: Does not constitute comprehensive employer establishment compliance verification."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint_type": self.endpoint_type.value,
            "identifier": self.identifier,
            "txn_id": self.txn_id,
            "status": self.status.value,
            "http_status": self.http_status,
            "format": self.format,
            "member_name": self.member_name,
            "dob": self.dob,
            "father_husband_name": self.father_husband_name,
            "certificate_number": self.certificate_number,
            "issue_date": self.issue_date,
            "issuer": self.issuer,
            "pdf_size_bytes": self.pdf_size_bytes,
            "raw_response": self.raw_response[:200] if self.raw_response else None,
            "response_hash": self.response_hash,
            "xml_field_paths": self.xml_field_paths,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "is_live": self.is_live,
            "is_employer_compliance": self.is_employer_compliance,
            "scope_notice": self.scope_notice,
        }
