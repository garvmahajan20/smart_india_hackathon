# -*- coding: utf-8 -*-
"""
API Setu / ESIC Verification Data Models.
Provides strongly typed models for requests, responses, status enums,
and validation logic strictly conforming to official API Setu specifications.

CRITICAL SCOPE DISTINCTION:
These models represent ESIC DOCUMENT/CERTIFICATE VERIFICATION ONLY.
They do NOT establish complete employer establishment compliance,
contribution/ECR filing compliance, or default history.
"""

import datetime
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ESICEndpointType(str, Enum):
    HEALTH_PASSBOOK = "HEALTH_PASSBOOK"   # Endpoint: /certificate/v3/esic/esich
    PEHCHAN_CARD = "PEHCHAN_CARD"         # Endpoint: /certificate/v3/esic/phcrd


class ESICVerificationStatus(str, Enum):
    """
    Normalized ESIC verification status outcomes.
    Distinct from tender compliance PASS/FAIL verdicts.
    """
    VERIFIED = "VERIFIED"                  # Authoritative external registry confirmed record
    NOT_VERIFIED = "NOT_VERIFIED"          # External registry record not found or data mismatch
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"# Valid certificate registered to different person/entity
    INVALID_REQUEST = "INVALID_REQUEST"    # Malformed parameter or syntax error
    ERROR = "ERROR"                        # Upstream gateway error (5xx, unexpected failure)
    UNAVAILABLE = "UNAVAILABLE"            # Timeout or network unreachable


def is_valid_ip_number(ip_no: Optional[str]) -> bool:
    """Insured Person (IP) Number is typically 10 to 17 numeric digits."""
    if not ip_no or not isinstance(ip_no, str):
        return False
    return bool(re.match(r"^[0-9]{10,17}$", ip_no.strip()))


def build_esic_consent_artifact(
    id_number: str,
    mobile: str = "9988776655",
    email: str = "test@email.com",
) -> Dict[str, Any]:
    """Builds standard consentArtifact structure for ESIC endpoints."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "consent": {
            "consentId": str(uuid.uuid4()),
            "timestamp": now_iso,
            "dataConsumer": {"id": "in.gov.sandbox"},
            "dataProvider": {"id": "in.gov.esic"},
            "purpose": {"description": "GeM Bidder ESIC Document Verification"},
            "user": {
                "idType": "ESIC_IP",
                "idNumber": str(id_number).strip(),
                "mobile": mobile,
                "email": email,
            },
            "data": {"id": "in.gov.esic"},
            "permission": {
                "access": "VIEW",
                "dateRange": {"from": now_iso, "to": now_iso},
                "frequency": {"unit": "ONETIME", "value": 1, "repeats": 0},
            },
        },
        "signature": {"signature": "SHA256withRSA_SIGNED_CONSENT"},
    }


@dataclass
class ESICHealthPassbookRequest:
    """
    Request model for ESIC Health Passbook endpoint.
    POST /certificate/v3/esic/esich
    CRITICAL: Preserves exact field casing: 'ipNumber' and 'RELATION'.
    """
    ip_number: str
    relation: str = "Self"                # e.g. Self, Spouse, Dependant mother, etc.
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def to_api_payload(self) -> Dict[str, Any]:
        clean_ip = self.ip_number.strip()
        consent = self.consent_artifact or build_esic_consent_artifact(clean_ip)
        return {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": {
                "ipNumber": clean_ip,             # EXACT CASING
                "RELATION": self.relation.strip(), # EXACT CASING
            },
            "consentArtifact": consent,
        }


@dataclass
class ESICPehchanCardRequest:
    """
    Request model for ESIC Pehchan Card endpoint.
    POST /certificate/v3/esic/phcrd
    CRITICAL: Preserves exact field casing: 'ipNumber' and 'EmployerName'.
    """
    ip_number: str
    employer_name: str = "Name"           # Employer name parameter
    format: str = "xml"
    txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consent_artifact: Optional[Dict[str, Any]] = None

    def to_api_payload(self) -> Dict[str, Any]:
        clean_ip = self.ip_number.strip()
        consent = self.consent_artifact or build_esic_consent_artifact(clean_ip)
        return {
            "txnId": self.txn_id,
            "format": self.format,
            "certificateParameters": {
                "ipNumber": clean_ip,                    # EXACT CASING
                "EmployerName": self.employer_name.strip(), # EXACT CASING
            },
            "consentArtifact": consent,
        }


@dataclass
class ESICVerificationResponse:
    """
    Unified normalized response structure for all ESIC verification transactions.
    Preserves exact external fields without fabricating missing ones.
    """
    endpoint_type: ESICEndpointType
    ip_number: str
    txn_id: str
    status: ESICVerificationStatus
    http_status: int
    format: str = "xml"
    insured_person_name: Optional[str] = None
    employer_name: Optional[str] = None
    dispensary: Optional[str] = None
    date_of_registration: Optional[str] = None
    relation: Optional[str] = None
    certificate_number: Optional[str] = None
    issuer: Optional[str] = "Employees State Insurance Corporation"
    raw_response: Optional[str] = None
    response_hash: Optional[str] = None
    xml_field_paths: Dict[str, str] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    is_live: bool = False

    # Mandatory scope limitation metadata
    is_employer_compliance: bool = False
    scope_notice: str = "ESIC_DOCUMENT_CERTIFICATE_VERIFICATION_ONLY: Verifies supplied Health Passbook / Pehchan Card record; does not independently establish complete employer ESIC compliance or contribution remittance history."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint_type": self.endpoint_type.value,
            "ip_number": self.ip_number,
            "txn_id": self.txn_id,
            "status": self.status.value,
            "http_status": self.http_status,
            "format": self.format,
            "insured_person_name": self.insured_person_name,
            "employer_name": self.employer_name,
            "dispensary": self.dispensary,
            "date_of_registration": self.date_of_registration,
            "relation": self.relation,
            "certificate_number": self.certificate_number,
            "issuer": self.issuer,
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
