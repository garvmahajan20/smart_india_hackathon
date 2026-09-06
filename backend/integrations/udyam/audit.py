# -*- coding: utf-8 -*-
"""
Audit Logger for API Setu Udyam Verification.
Enforces strict ZERO SECRET LEAKAGE:
- Never logs API keys, client secrets, or authorization credentials.
- Masks Udyam numbers (e.g. UDYAM-MH-01-***8776) and mobile numbers.
- Replaces raw credentials with deterministic SHA-256 digests.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional


def hash_secret(secret: Optional[str]) -> str:
    if not secret:
        return "none"
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def mask_udyam(udyam: Optional[str]) -> str:
    if not udyam:
        return "none"
    u = udyam.strip().upper()
    if len(u) >= 15:
        # e.g. UDYAM-MH-01-***8776
        return f"{u[:12]}***{u[-4:]}"
    return "****"


def mask_mobile(mobile: Optional[str]) -> str:
    if not mobile:
        return "none"
    m = str(mobile).strip()
    if len(m) >= 10:
        return f"******{m[-4:]}"
    return "******"


@dataclass
class UdyamAuditEvent:
    event_id: str
    event_type: str
    status: str
    timestamp: str
    txn_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "status": self.status,
            "timestamp": self.timestamp,
            "txn_id": self.txn_id,
            "details": self.details,
        }


class UdyamAuditLogger:
    """
    Thread-safe deterministic audit logger with bounded memory buffer for Udyam calls.
    """
    def __init__(self, max_buffer_size: int = 1000):
        self.max_buffer_size = max_buffer_size
        self._events: List[UdyamAuditEvent] = []
        self._lock = Lock()
        self._seq = 0

    def log(
        self,
        event_type: str,
        status: str,
        txn_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> UdyamAuditEvent:
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._seq += 1
            event_id = f"UDYAM-AUDIT-{self._seq:06d}"
            safe_details = self._sanitize(details or {})

            event = UdyamAuditEvent(
                event_id=event_id,
                event_type=event_type,
                status=status,
                timestamp=now_utc,
                txn_id=txn_id,
                details=safe_details,
            )

            self._events.append(event)
            if len(self._events) > self.max_buffer_size:
                self._events.pop(0)

            return event

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        scrubbed = {}
        sensitive_keys = {"api_key", "apikey", "secret", "password", "authorization", "token"}
        for k, v in data.items():
            lower_k = k.lower()
            if lower_k.endswith("_hash"):
                scrubbed[k] = v
            elif any(sk in lower_k for sk in sensitive_keys):
                if isinstance(v, str) and v:
                    scrubbed[f"{k}_hash"] = hash_secret(v)
                else:
                    scrubbed[k] = "[REDACTED]"
            elif "udyam" in lower_k and isinstance(v, str):
                scrubbed[k] = mask_udyam(v)
            elif "mobile" in lower_k and isinstance(v, str):
                scrubbed[k] = mask_mobile(v)
            elif isinstance(v, dict):
                scrubbed[k] = self._sanitize(v)
            else:
                scrubbed[k] = v
        return scrubbed

    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if event_type:
                return [e.to_dict() for e in self._events if e.event_type == event_type]
            return [e.to_dict() for e in self._events]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._seq = 0


default_udyam_audit_logger = UdyamAuditLogger()
