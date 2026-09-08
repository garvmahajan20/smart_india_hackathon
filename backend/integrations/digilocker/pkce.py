# -*- coding: utf-8 -*-
"""
PKCE (Proof Key for Code Exchange) Cryptographic Helpers and State Store.
Strictly implements RFC 7636 and OAuth 2.0 security best practices.
"""

import base64
import hashlib
import hmac
import secrets
import time
from threading import Lock
from typing import Any, Dict, Optional


def generate_code_verifier(length: int = 64) -> str:
    """
    Generates a cryptographically secure random code_verifier for PKCE.
    RFC 7636 requires:
    - Minimum length: 43 characters
    - Maximum length: 128 characters
    - Characters: [A-Z], [a-z], [0-9], "-", ".", "_", "~"
    """
    if length < 43 or length > 128:
        raise ValueError(f"PKCE code_verifier length must be between 43 and 128 (received {length})")

    # Generate random URL-safe string and trim/pad to requested length
    raw = secrets.token_urlsafe(length + 16)
    raw = raw.replace("=", "")
    return raw[:length]


def generate_code_challenge(verifier: str) -> str:
    """
    Derives the S256 code_challenge from a code_verifier according to RFC 7636:
    code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier))) without padding '='.
    """
    if not verifier:
        raise ValueError("code_verifier cannot be empty")

    sha256_hash = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(sha256_hash).decode("ascii").rstrip("=")
    return challenge


def generate_state(nbytes: int = 32) -> str:
    """
    Generates a cryptographically secure random state parameter for CSRF mitigation.
    """
    return secrets.token_urlsafe(nbytes)


def verify_code_challenge(verifier: str, challenge: str) -> bool:
    """
    Validates a code_verifier against an expected S256 code_challenge using constant-time comparison.
    """
    if not verifier or not challenge:
        return False
    calculated = generate_code_challenge(verifier)
    return hmac.compare_digest(calculated, challenge)


class PKCEStateStore:
    """
    Thread-safe in-memory store for pending PKCE verifiers and authorization states.
    Includes TTL expiration to prevent state replay and memory accumulation.
    """
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def store(self, state: str, verifier: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Records state and code_verifier with current timestamp.
        """
        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            self._store[state] = {
                "verifier": verifier,
                "created_at": now,
                "metadata": metadata or {},
            }

    def pop(self, state: str) -> Optional[str]:
        """
        Retrieves and removes the verifier associated with state (one-time use).
        Returns None if state is invalid or expired.
        """
        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            entry = self._store.pop(state, None)
            if entry and (now - entry["created_at"]) <= self.ttl_seconds:
                return entry["verifier"]
            return None

    def peek(self, state: str) -> Optional[Dict[str, Any]]:
        """
        Inspects state entry without removing it.
        """
        now = time.time()
        with self._lock:
            entry = self._store.get(state)
            if entry and (now - entry["created_at"]) <= self.ttl_seconds:
                return entry
            return None

    def _cleanup_expired(self, now: float) -> None:
        """
        Purges expired entries. Must be called with self._lock held.
        """
        expired = [s for s, data in self._store.items() if (now - data["created_at"]) > self.ttl_seconds]
        for s in expired:
            self._store.pop(s, None)

    def clear(self) -> None:
        """
        Clears all stored states.
        """
        with self._lock:
            self._store.clear()


# Global default state store instance
default_pkce_store = PKCEStateStore(ttl_seconds=600)
