# -*- coding: utf-8 -*-
"""
API Setu / ESIC Verification Integration Package.
Provides unified client and adapters for:
1. Health Passbook (esich)
2. Pehchan Card (phcrd)
"""

from .audit import (
    ESICAuditEvent,
    ESICAuditLogger,
    default_esic_audit_logger,
    hash_secret,
    mask_ip_number,
)
from .client import (
    APISetuESICClient,
    ESICClientAuthError,
    ESICClientError,
    ESICClientNetworkError,
)
from .config import ESICVerificationConfig
from .evidence_adapter import APISetuESICEvidenceAdapter
from .models import (
    ESICEndpointType,
    ESICHealthPassbookRequest,
    ESICPehchanCardRequest,
    ESICVerificationResponse,
    ESICVerificationStatus,
    is_valid_ip_number,
)
from .xml_parser import ESICXMLParsingError, parse_esic_certificate_xml

ESICDocumentType = ESICEndpointType
parse_esic_verification_xml = parse_esic_certificate_xml

__all__ = [
    "ESICVerificationConfig",
    "ESICEndpointType",
    "ESICVerificationStatus",
    "ESICHealthPassbookRequest",
    "ESICPehchanCardRequest",
    "ESICVerificationResponse",
    "is_valid_ip_number",
    "ESICAuditLogger",
    "ESICAuditEvent",
    "default_esic_audit_logger",
    "hash_secret",
    "mask_ip_number",
    "ESICXMLParsingError",
    "parse_esic_certificate_xml",
    "ESICClientError",
    "ESICClientAuthError",
    "ESICClientNetworkError",
    "APISetuESICClient",
    "APISetuESICEvidenceAdapter",
]
