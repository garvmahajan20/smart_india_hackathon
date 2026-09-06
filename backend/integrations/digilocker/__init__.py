# -*- coding: utf-8 -*-
"""
DigiLocker / API Setu Sandbox Integration Package.
Production-grade integration layer for real-world government document and credential verification.
"""

from .audit import (
    DigiLockerAuditEvent,
    DigiLockerAuditLogger,
    default_audit_logger,
    hash_token,
    mask_sensitive_id,
)
from .client import (
    DigiLockerAuthError,
    DigiLockerClientError,
    DigiLockerNetworkError,
    DigiLockerSandboxClient,
)
from .config import DigiLockerConfig
from .evidence_adapter import DigiLockerEvidenceAdapter
from .models import (
    DigiLockerDocumentItem,
    DigiLockerParsedCertificate,
    DigiLockerPulledDocument,
    DigiLockerTokenResponse,
    DigiLockerUserDetails,
)
from .pkce import (
    PKCEStateStore,
    default_pkce_store,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
    verify_code_challenge,
)
from .xml_parser import (
    DigiLockerXMLParsingError,
    parse_digilocker_certificate_xml,
    parse_pull_doc_response,
)

__all__ = [
    "DigiLockerConfig",
    "DigiLockerSandboxClient",
    "DigiLockerClientError",
    "DigiLockerAuthError",
    "DigiLockerNetworkError",
    "DigiLockerTokenResponse",
    "DigiLockerUserDetails",
    "DigiLockerDocumentItem",
    "DigiLockerParsedCertificate",
    "DigiLockerPulledDocument",
    "DigiLockerEvidenceAdapter",
    "DigiLockerAuditLogger",
    "DigiLockerAuditEvent",
    "default_audit_logger",
    "hash_token",
    "mask_sensitive_id",
    "generate_code_verifier",
    "generate_code_challenge",
    "generate_state",
    "verify_code_challenge",
    "PKCEStateStore",
    "default_pkce_store",
    "parse_digilocker_certificate_xml",
    "parse_pull_doc_response",
    "DigiLockerXMLParsingError",
]
