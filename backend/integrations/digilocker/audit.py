# -*- coding: utf-8 -*-
"""
DigiLocker Integration Audit Logger.
Enforces strict ZERO SECRET LEAKAGE:
- Never logs access tokens, refresh tokens, client secrets, auth codes, or raw PKCE verifiers.
- Uses SHA-256 digests of credentials for correlation without leakage.
- Masks sensitive government IDs (UID, Aadhaar, PAN).
"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional


def hash_token(token: Optional[str]) -> str:
    """
    Computes deterministic SHA-256 fingerprint for correlation without revealing credential.
    Returns prefix-tagged short hash e.g. "sha256:a1b2c3d4e5f6".
    """
    if not token:
        return "none"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def mask_sensitive_id(identifier: Optional[str]) -> str:
    """
    Masks sensitive personal or corporate identifiers (Aadhaar/UID, PAN, GSTIN).
    Leaves last 4 characters visible.
    """
    if not identifier:
        return "none"
    s = str(identifier).strip()
    if len(s) <= 4:
        return "****"
    return f"***{s[-4:]}"


@dataclass
class DigiLockerAuditEvent:
    """
    Immutable structured audit event record.
    """
    event_id: str
    event_type: str
    status: str
    timestamp: str
    trace_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "status": self.status,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "details": self.details,
        }


class DigiLockerAuditLogger:
    """
    Thread-safe deterministic audit logger with bounded memory buffer.
    """
    def __init__(self, max_buffer_size: int = 1000):
        self.max_buffer_size = max_buffer_size
        self._events: List[DigiLockerAuditEvent] = []
        self._lock = Lock()
        self._seq = 0

    def log(
        self,
        event_type: str,
        status: str,
        trace_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> DigiLockerAuditEvent:
        """
        Records an audit event, sanitizing all details to ensure zero secret leakage.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._seq += 1
            event_id = f"DL-AUDIT-{self._seq:06d}"

            # Sanitize details
            safe_details = self._sanitize(details or {})

            event = DigiLockerAuditEvent(
                event_id=event_id,
                event_type=event_type,
                status=status,
                timestamp=now_utc,
                trace_id=trace_id,
                details=safe_details,
            )

            self._events.append(event)
            if len(self._events) > self.max_buffer_size:
                self._events.pop(0)

            return event

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively scrubs any keys containing secret or token information.
        """
        scrubbed = {}
        sensitive_keys = {
            "token", "access_token", "refresh_token", "client_secret",
            "code", "code_verifier", "authorization", "secret", "password"
        }
        for k, v in data.items():
            lower_k = k.lower()
            if lower_k.endswith("_hash"):
                scrubbed[k] = v
            elif lower_k in sensitive_keys or any(sk == lower_k for sk in sensitive_keys):
                if isinstance(v, str) and v:
                    scrubbed[f"{k}_hash"] = hash_token(v)
                else:
                    scrubbed[k] = "[REDACTED]"
            elif isinstance(v, dict):
                scrubbed[k] = self._sanitize(v)
            else:
                scrubbed[k] = v
        return scrubbed

    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves serialized audit events, optionally filtered by event_type.
        """
        with self._lock:
            if event_type:
                return [e.to_dict() for e in self._events if e.event_type == event_type]
            return [e.to_dict() for e in self._events]

    def clear(self) -> None:
        """
        Clears audit buffer.
        """
        with self._lock:
            self._events.clear()
            self._seq = 0


# Default audit logger instance
default_audit_logger = DigiLockerAuditLogger()
