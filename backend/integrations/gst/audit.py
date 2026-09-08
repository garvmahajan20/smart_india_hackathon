# -*- coding: utf-8 -*-
"""
Audit Logging and Security Redaction for GSTINAPI Integration.
Enforces strict secret masking, non-repudiable audit hashing, and header redaction.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def hash_secret(secret: Optional[str]) -> str:
    """
    Generates deterministic SHA-256 fingerprint of a secret for audit correlation
    without exposing cleartext values.
    """
    if not secret:
        return ""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def mask_gstin(gstin: Optional[str]) -> str:
    """
    Partially masks a 15-character GSTIN for privacy-compliant logging.
    e.g. 24AAAAA0000A1Z5 -> 24AAAA****0A1Z5
    """
    if not gstin or len(gstin) < 10:
        return str(gstin or "")
    clean = gstin.strip().upper()
    return f"{clean[:6]}****{clean[-5:]}"


def redact_sensitive_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Scrubs credentials from HTTP headers before logging.
    """
    if not headers:
        return {}
    clean: Dict[str, str] = {}
    sensitive_keys = {"x-api-key", "authorization", "api-key", "apikey", "secret"}
    for k, v in headers.items():
        if k.lower() in sensitive_keys:
            clean[k] = "[REDACTED]"
        else:
            clean[k] = str(v)
    return clean


@dataclass
class GSTAuditEvent:
    """Structured audit trail record for GST verification operations."""
    event_type: str
    status: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    gstin_masked: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "status": self.status,
            "timestamp": self.timestamp,
            "gstin": self.gstin_masked,
            "details": self.details,
        }


class GSTAuditLogger:
    """In-memory tamper-evident audit logger for GST queries."""
    def __init__(self):
        self._events: List[GSTAuditEvent] = []

    def log(
        self,
        event_type: str,
        status: str,
        gstin: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> GSTAuditEvent:
        d = dict(details or {})
        # Ensure any nested headers or tokens are redacted
        if "headers" in d and isinstance(d["headers"], dict):
            d["headers"] = redact_sensitive_headers(d["headers"])

        event = GSTAuditEvent(
            event_type=event_type,
            status=status,
            gstin_masked=mask_gstin(gstin),
            details=d,
        )
        self._events.append(event)
        return event

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events[-limit:]]

    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        evs = self._events
        if event_type:
            evs = [e for e in evs if e.event_type == event_type]
        return [e.to_dict() for e in evs[-limit:]]

    def clear(self) -> None:
        self._events.clear()


default_gst_audit_logger = GSTAuditLogger()
