# -*- coding: utf-8 -*-
"""
API Setu / Income Tax Department PAN Verification Package.
Production-grade integration for official PAN Verification Record (PANCR).
"""

from .audit import PANAuditEvent, PANAuditLogger, default_pan_audit_logger, hash_secret, mask_pan
from .client import (
    APISetuPANClient,
    PANClientAuthError,
    PANClientError,
    PANClientNetworkError,
)
from .config import PANVerificationConfig
from .evidence_adapter import APISetuPANEvidenceAdapter
from .models import (
    PANVerificationRequest,
    PANVerificationResponse,
    PANVerificationStatus,
    is_valid_pan_format,
)
from .xml_parser import PANXMLParsingError, parse_pan_verification_xml

__all__ = [
    "PANVerificationConfig",
    "APISetuPANClient",
    "PANClientError",
    "PANClientAuthError",
    "PANClientNetworkError",
    "PANVerificationRequest",
    "PANVerificationResponse",
    "PANVerificationStatus",
    "is_valid_pan_format",
    "APISetuPANEvidenceAdapter",
    "PANAuditLogger",
    "PANAuditEvent",
    "default_pan_audit_logger",
    "hash_secret",
    "mask_pan",
    "parse_pan_verification_xml",
    "PANXMLParsingError",
]
