# -*- coding: utf-8 -*-
"""
API Setu / EPFO Verification Integration Package.
Provides unified client and adapters for:
1. UAN Card (PDF)
2. Scheme Certificate (XML)
3. Pension Certificate (XML)
"""

from .audit import (
    EPFOAuditEvent,
    EPFOAuditLogger,
    default_epfo_audit_logger,
    hash_secret,
    mask_identifier,
)
from .client import (
    APISetuEPFOClient,
    EPFOClientAuthError,
    EPFOClientError,
    EPFOClientNetworkError,
)
from .config import EPFOVerificationConfig
from .evidence_adapter import APISetuEPFOEvidenceAdapter
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

__all__ = [
    "EPFOVerificationConfig",
    "EPFOEndpointType",
    "EPFOVerificationStatus",
    "UANCardRequest",
    "SchemeCertificateRequest",
    "PensionCertificateRequest",
    "EPFOVerificationResponse",
    "is_valid_uan_format",
    "is_valid_dob_format",
    "is_valid_scno_format",
    "is_valid_ppono_format",
    "EPFOAuditLogger",
    "EPFOAuditEvent",
    "default_epfo_audit_logger",
    "hash_secret",
    "mask_identifier",
    "EPFOXMLParsingError",
    "parse_epfo_certificate_xml",
    "EPFOPDFHandlingError",
    "process_epfo_uan_pdf",
    "EPFOClientError",
    "EPFOClientAuthError",
    "EPFOClientNetworkError",
    "APISetuEPFOClient",
    "APISetuEPFOEvidenceAdapter",
]
