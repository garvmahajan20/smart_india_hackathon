# -*- coding: utf-8 -*-
"""
GSTINAPI Integration Package.
Provides typed client, configuration, audit logging, data models,
and evidence adapters for GST verification and return filing compliance.
"""

from .config import GSTINAPIConfig
from .audit import (
    GSTAuditEvent,
    GSTAuditLogger,
    default_gst_audit_logger,
    hash_secret,
    mask_gstin,
    redact_sensitive_headers,
)
from .models import (
    GSTComplianceSummary,
    GSTFilingPreference,
    GSTReturnRecord,
    GSTTaxpayerData,
    GSTVerificationRequest,
    GSTVerificationResponse,
    GSTVerificationStatus,
    extract_pan_from_gstin,
    is_valid_gstin_format,
)
from .client import GSTINAPIClient
from .evidence_adapter import GSTINAPIEvidenceAdapter, GSTINAPIGovernmentAdapter

__all__ = [
    "GSTINAPIConfig",
    "GSTAuditEvent",
    "GSTAuditLogger",
    "default_gst_audit_logger",
    "hash_secret",
    "mask_gstin",
    "redact_sensitive_headers",
    "GSTComplianceSummary",
    "GSTFilingPreference",
    "GSTReturnRecord",
    "GSTTaxpayerData",
    "GSTVerificationRequest",
    "GSTVerificationResponse",
    "GSTVerificationStatus",
    "extract_pan_from_gstin",
    "is_valid_gstin_format",
    "GSTINAPIClient",
    "GSTINAPIEvidenceAdapter",
    "GSTINAPIGovernmentAdapter",
]
