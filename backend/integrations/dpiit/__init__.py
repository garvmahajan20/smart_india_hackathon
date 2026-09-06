# -*- coding: utf-8 -*-
"""
API Setu / DPIIT Startup India Recognition Certificate Integration Package.
"""

from .audit import (
    DPIITAuditEvent,
    DPIITAuditLogger,
    default_dpiit_audit_logger,
    hash_secret,
    mask_mobile,
    mask_regn,
)
from .client import (
    APISetuDPIITClient,
    DPIITClientAuthError,
    DPIITClientError,
    DPIITClientNetworkError,
)
from .config import DPIITVerificationConfig
from .evidence_adapter import APISetuDPIITEvidenceAdapter
from .models import (
    DPIITVerificationRequest,
    DPIITVerificationResponse,
    DPIITVerificationStatus,
    is_valid_dpiit_regn,
    is_valid_mobile_format,
)
from .xml_parser import DPIITXMLParsingError, parse_dpiit_recognition_xml

is_valid_dpiit_format = is_valid_dpiit_regn
mask_registration = mask_regn
parse_dpiit_verification_xml = parse_dpiit_recognition_xml

__all__ = [
    "DPIITVerificationConfig",
    "DPIITVerificationStatus",
    "DPIITVerificationRequest",
    "DPIITVerificationResponse",
    "is_valid_dpiit_regn",
    "is_valid_mobile_format",
    "DPIITAuditLogger",
    "DPIITAuditEvent",
    "default_dpiit_audit_logger",
    "hash_secret",
    "mask_regn",
    "mask_mobile",
    "DPIITXMLParsingError",
    "parse_dpiit_recognition_xml",
    "DPIITClientError",
    "DPIITClientAuthError",
    "DPIITClientNetworkError",
    "APISetuDPIITClient",
    "APISetuDPIITEvidenceAdapter",
]
