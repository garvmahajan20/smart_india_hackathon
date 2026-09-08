# -*- coding: utf-8 -*-
"""
Typed HTTP Client for GSTINAPI.
Implements:
- GET /v1/gstin/{gstin}
- GET /v1/gstin/{gstin}?include=profile
- GET /v1/gstin/{gstin}/returns?fy=YYYY-YY
- GET /v1/gstin/{gstin}/filing-preference?fy=YYYY-YY
- GET /v1/gstin/{gstin}/compliance?fy=YYYY-YY
- GET /v1/gstin/stats/me

Guarantees:
- Never exposes API keys in logs, exceptions, or responses.
- Enforces strict input validation to avoid burning credits on typos.
- Retries ONLY on 429 and 502 with exponential backoff (max 2 retries).
- Never retries 400, 401, 402, 403, 404.
- In-memory request caching per client instance to prevent duplicate billable calls.
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from .audit import GSTAuditLogger, default_gst_audit_logger, redact_sensitive_headers
from .config import GSTINAPIConfig
from .models import (
    GSTComplianceSummary,
    GSTFilingPreference,
    GSTReturnRecord,
    GSTTaxpayerData,
    GSTVerificationRequest,
    GSTVerificationResponse,
    GSTVerificationStatus,
    is_valid_gstin_format,
)


class GSTINAPIClient:
    """Client for authentic GST verification via GSTINAPI."""

    def __init__(
        self,
        config: Optional[GSTINAPIConfig] = None,
        audit_logger: Optional[GSTAuditLogger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or GSTINAPIConfig.from_env()
        self.audit_logger = audit_logger or default_gst_audit_logger
        self.session = session or requests.Session()
        self._lookup_cache: Dict[str, GSTVerificationResponse] = {}

    def clear_cache(self) -> None:
        """Clears the in-memory request cache."""
        self._lookup_cache.clear()

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.config.api_key,
            "Accept": "application/json",
            "User-Agent": "GeM-Bid-Compliance-Engine/1.0",
        }

    def _request_with_retry(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[Dict[str, Any]], float, Optional[str]]:
        """
        Executes HTTP GET with deterministic backoff.
        Only retries 429 (rate limit) and 502 (gateway failure).
        """
        url = f"{self.config.base_url.rstrip('/')}{endpoint}"
        headers = self._headers()
        t0 = time.perf_counter()

        max_attempts = max(1, self.config.max_retries + 1)
        last_error = None
        last_status = 500
        last_json = None

        for attempt in range(max_attempts):
            try:
                resp = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
                latency = (time.perf_counter() - t0) * 1000.0
                last_status = resp.status_code

                try:
                    data = resp.json()
                    if not isinstance(data, (dict, list)):
                        data = None
                except Exception:
                    data = None

                last_json = data

                # Success or non-retryable error
                if resp.status_code not in (429, 502):
                    return resp.status_code, data, latency, None

                # Retryable error: 429 or 502
                if attempt < max_attempts - 1:
                    backoff = self.config.retry_backoff_factor * (2 ** attempt)
                    time.sleep(backoff)
                    continue

                return resp.status_code, data, latency, f"HTTP {resp.status_code} received after {max_attempts} attempts"

            except (requests.Timeout, requests.ConnectionError) as ex:
                last_error = type(ex).__name__
                if attempt < max_attempts - 1:
                    time.sleep(self.config.retry_backoff_factor)
                    continue

        latency = (time.perf_counter() - t0) * 1000.0
        return 504, None, latency, f"Network timeout/unreachable: {last_error}"

    def lookup(
        self,
        gstin: str,
        include_profile: bool = True,
    ) -> GSTVerificationResponse:
        """
        Core GSTIN registration lookup.
        GET /v1/gstin/{gstin}?include=profile
        """
        clean_gst = gstin.strip().upper() if gstin else ""
        cache_key = f"{clean_gst}:{include_profile}"

        if self.config.cache_enabled and cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        # 1. Syntax Validation (Pre-flight to prevent credit waste)
        if not is_valid_gstin_format(clean_gst):
            self.audit_logger.log(
                event_type="GST_LOOKUP_REJECTED",
                status="INVALID_FORMAT",
                gstin=clean_gst,
                details={"reason": "Invalid 15-character GSTIN regex format"},
            )
            return GSTVerificationResponse(
                gstin=clean_gst,
                status=GSTVerificationStatus.UNVERIFIED,
                http_status=400,
                error_code="INVALID_GSTIN_FORMAT",
                error_message="Invalid GSTIN format: does not conform to standard format (2 digits, 10 PAN characters, 1 entity code, 'Z', 1 check character).",
                is_live=False,
            )

        # 2. Configuration Check
        if not self.config.is_configured():
            self.audit_logger.log(
                event_type="GST_LOOKUP_UNCONFIGURED",
                status="AUTH_ERROR",
                gstin=clean_gst,
                details={"reason": "GSTINAPI API key is not configured"},
            )
            return GSTVerificationResponse(
                gstin=clean_gst,
                status=GSTVerificationStatus.AUTH_ERROR,
                http_status=401,
                error_code="UNCONFIGURED",
                error_message="GSTINAPI API key is not configured in backend environment.",
                is_live=False,
            )

        # 3. Execute HTTP Call
        endpoint = f"/v1/gstin/{clean_gst}"
        params = {"include": "profile"} if include_profile else None

        self.audit_logger.log(
            event_type="GST_LOOKUP_INITIATED",
            status="INITIATED",
            gstin=clean_gst,
            details={"endpoint": endpoint, "include_profile": include_profile},
        )

        status_code, data, latency_ms, err_detail = self._request_with_retry(endpoint, params=params)

        # Compute deterministic response hash
        resp_str = json.dumps(data, sort_keys=True) if data else (err_detail or "")
        resp_hash = hashlib.sha256(resp_str.encode("utf-8")).hexdigest()

        # Handle Responses
        if status_code == 200 and data and (data.get("success") or "legal_name" in data or "data" in data):
            tp_dict = data.get("data", data) if isinstance(data, dict) else {}
            profile_complete = data.get("profile_complete", False) if isinstance(data, dict) else False
            tp_data = GSTTaxpayerData.from_dict(tp_dict, profile_complete=profile_complete)

            # Determine registration status
            raw_status = (tp_data.status or "").strip().lower()
            if raw_status in ("cancelled", "canceled"):
                v_status = GSTVerificationStatus.CANCELLED
            elif raw_status == "suspended":
                v_status = GSTVerificationStatus.SUSPENDED
            else:
                v_status = GSTVerificationStatus.VERIFIED

            is_test = bool(data.get("test") or data.get("billed_to") == "test")
            credits_rem = data.get("credits_remaining")

            res = GSTVerificationResponse(
                gstin=clean_gst,
                status=v_status,
                http_status=200,
                data=tp_data,
                credits_remaining=credits_rem,
                response_ms=latency_ms,
                response_hash=resp_hash,
                is_live=True,
                is_test=is_test,
                raw_response=data,
            )
            if self.config.cache_enabled:
                self._lookup_cache[cache_key] = res
            self.audit_logger.log(
                event_type="GST_LOOKUP_SUCCESS",
                status=v_status.value,
                gstin=clean_gst,
                details={"legal_name": tp_data.legal_name, "status": tp_data.status, "credits_remaining": credits_rem},
            )
            return res

        # Error Mapping
        if status_code == 404:
            v_status = GSTVerificationStatus.NOT_VERIFIED
            err_msg = data.get("error", "GSTIN not registered in government database.") if data else "GSTIN not found."
        elif status_code == 400:
            v_status = GSTVerificationStatus.UNVERIFIED
            err_msg = data.get("error", "Invalid GSTIN format rejected by provider.") if data else "Bad request."
        elif status_code in (401, 403):
            v_status = GSTVerificationStatus.AUTH_ERROR
            err_msg = "Authentication failed: invalid or deactivated GSTINAPI key."
        elif status_code == 402:
            v_status = GSTVerificationStatus.QUOTA_EXHAUSTED
            err_msg = "GSTINAPI account credits exhausted."
        elif status_code == 429:
            v_status = GSTVerificationStatus.RATE_LIMITED
            err_msg = "GSTINAPI rate limit exceeded (60 requests/min)."
        else:
            v_status = GSTVerificationStatus.SERVICE_UNAVAILABLE
            err_msg = err_detail or f"Provider upstream gateway error (HTTP {status_code})."

        self.audit_logger.log(
            event_type="GST_LOOKUP_FAILURE",
            status=v_status.value,
            gstin=clean_gst,
            details={"http_status": status_code, "error": err_msg},
        )

        res = GSTVerificationResponse(
            gstin=clean_gst,
            status=v_status,
            http_status=status_code,
            error_code=f"HTTP_{status_code}",
            error_message=err_msg,
            response_ms=latency_ms,
            response_hash=resp_hash,
            is_live=False,
            raw_response=data,
        )
        if self.config.cache_enabled:
            self._lookup_cache[cache_key] = res
        return res

    def get_returns(self, gstin: str, fy: str = "2024-25") -> List[GSTReturnRecord]:
        """
        Retrieves return filing records for a financial year (e.g., '2024-25').
        GET /v1/gstin/{gstin}/returns?fy=YYYY-YY
        """
        clean_gst = gstin.strip().upper() if gstin else ""
        if not is_valid_gstin_format(clean_gst) or not self.config.is_configured():
            return []

        endpoint = f"/v1/gstin/{clean_gst}/returns"
        status_code, data, _, _ = self._request_with_retry(endpoint, params={"fy": fy})

        if status_code == 200 and data:
            returns_raw = data.get("returns", []) if isinstance(data, dict) else []
            return [GSTReturnRecord.from_dict(r) for r in returns_raw]

        return []

    def get_filing_preference(self, gstin: str, fy: str = "2024-25") -> List[GSTFilingPreference]:
        """
        Retrieves QRMP monthly/quarterly preference.
        GET /v1/gstin/{gstin}/filing-preference?fy=YYYY-YY
        """
        clean_gst = gstin.strip().upper() if gstin else ""
        if not is_valid_gstin_format(clean_gst) or not self.config.is_configured():
            return []

        endpoint = f"/v1/gstin/{clean_gst}/filing-preference"
        status_code, data, _, _ = self._request_with_retry(endpoint, params={"fy": fy})

        if status_code == 200 and data:
            prefs_raw = data.get("filing_preference", []) if isinstance(data, dict) else []
            return [GSTFilingPreference.from_dict(p) for p in prefs_raw]

        return []

    def get_compliance(self, gstin: str, fy: str = "2024-25") -> Optional[GSTComplianceSummary]:
        """
        Retrieves filing compliance summary for a financial year.
        GET /v1/gstin/{gstin}/compliance?fy=YYYY-YY
        """
        clean_gst = gstin.strip().upper() if gstin else ""
        if not is_valid_gstin_format(clean_gst) or not self.config.is_configured():
            return None

        endpoint = f"/v1/gstin/{clean_gst}/compliance"
        status_code, data, _, _ = self._request_with_retry(endpoint, params={"fy": fy})

        if status_code == 200 and data:
            comp_dict = data.get("compliance", {}) if isinstance(data, dict) else {}
            return GSTComplianceSummary.from_dict(comp_dict)

        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Diagnostic check for account API usage. Never exposed to bidders.
        GET /v1/gstin/stats/me
        """
        if not self.config.is_configured():
            return {"error": "Unconfigured"}
        status_code, data, _, err = self._request_with_retry("/v1/gstin/stats/me")
        if status_code == 200 and data:
            return data
        return {"error": err or f"HTTP {status_code}"}

    def verify_gstin(
        self,
        request: Union[GSTVerificationRequest, str],
        include_profile: bool = True,
        check_returns: bool = False,
        fy: Optional[str] = None,
    ) -> GSTVerificationResponse:
        """
        Comprehensive verification workflow coordinating lookup and optional return history.
        Supports passing either a GSTVerificationRequest object or raw string identifier.
        """
        if isinstance(request, str):
            req_obj = GSTVerificationRequest(
                gstin=request,
                include_profile=include_profile,
                check_returns=check_returns,
                financial_year=fy,
            )
        else:
            req_obj = request

        clean_gst = req_obj.clean_gstin()
        resp = self.lookup(clean_gst, include_profile=req_obj.include_profile)

        # If returns check requested and primary lookup succeeded
        if req_obj.check_returns and resp.status == GSTVerificationStatus.VERIFIED and req_obj.financial_year:
            fy_val = req_obj.financial_year
            resp.fy = fy_val
            resp.returns = self.get_returns(clean_gst, fy_val)
            resp.filing_preference = self.get_filing_preference(clean_gst, fy_val)
            resp.compliance = self.get_compliance(clean_gst, fy_val)

        return resp
