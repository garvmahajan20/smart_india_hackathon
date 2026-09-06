# -*- coding: utf-8 -*-
"""
Audit Logger for API Setu ESIC Verification.
Enforces strict ZERO SECRET LEAKAGE:
- Never logs API keys, client secrets, or authorization credentials.
- Masks IP numbers (e.g. 1199****0090).
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


def mask_ip_number(ip: Optional[str]) -> str:
    if not ip:
        return "none"
    s = str(ip).strip()
    if len(s) >= 8:
        return f"{s[:4]}****{s[-4:]}"
    return "****"


@dataclass
class ESICAuditEvent:
    event_id: str
    event_type: str
    endpoint_type: str
    status: str
    timestamp: str
    txn_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "endpoint_type": self.endpoint_type,
            "status": self.status,
            "timestamp": self.timestamp,
            "txn_id": self.txn_id,
            "details": self.details,
        }


class ESICAuditLogger:
    """
    Thread-safe deterministic audit logger with bounded memory buffer for ESIC calls.
    """
    def __init__(self, max_buffer_size: int = 1000):
        self.max_buffer_size = max_buffer_size
        self._events: List[ESICAuditEvent] = []
        self._lock = Lock()
        self._seq = 0

    def log(
        self,
        event_type: str,
        endpoint_type: str,
        status: str,
        txn_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ESICAuditEvent:
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._seq += 1
            event_id = f"ESIC-AUDIT-{self._seq:06d}"
            safe_details = self._sanitize(details or {})

            event = ESICAuditEvent(
                event_id=event_id,
                event_type=event_type,
                endpoint_type=endpoint_type,
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
            elif "ip" in lower_k and isinstance(v, str):
                scrubbed[k] = mask_ip_number(v)
            elif isinstance(v, dict):
                scrubbed[k] = self._sanitize(v)
            else:
                scrubbed[k] = v
        return scrubbed

    def get_events(self, endpoint_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if endpoint_type:
                return [e.to_dict() for e in self._events if e.endpoint_type == endpoint_type]
            return [e.to_dict() for e in self._events]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._seq = 0


default_esic_audit_logger = ESICAuditLogger()
