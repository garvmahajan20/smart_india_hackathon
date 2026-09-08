# -*- coding: utf-8 -*-
"""
Data models for GSTINAPI (GST verification and return filing).
Converts external provider responses into strongly-typed internal structures.
"""

import re
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

# Official 15-character GSTIN format:
# 2 state digits + 5 PAN letters + 4 PAN digits + 1 PAN letter + 1 entity code + 1 'Z' + 1 check character
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


def is_valid_gstin_format(gstin: Optional[str]) -> bool:
    """
    Validates GSTIN structure against statutory regex.
    Prevents making billable external requests for malformed inputs.
    """
    if not gstin or not isinstance(gstin, str):
        return False
    return bool(GSTIN_REGEX.match(gstin.strip().upper()))


def extract_pan_from_gstin(gstin: Optional[str]) -> Optional[str]:
    """
    Extracts the 10-character PAN embedded in chars 3-12 of a 15-char GSTIN.
    """
    if not gstin or len(gstin.strip()) != 15:
        return None
    return gstin.strip().upper()[2:12]


class GSTVerificationStatus(str, Enum):
    """
    Standardized GST verification outcomes.
    """
    VERIFIED = "VERIFIED"                  # Active/valid taxpayer confirmed in registry
    NOT_VERIFIED = "NOT_VERIFIED"          # GSTIN not registered (404)
    UNVERIFIED = "UNVERIFIED"              # Input format invalid (400)
    UNAVAILABLE = "UNAVAILABLE"            # Upstream 502 or timeout
    SERVICE_UNAVAILABLE = "UNAVAILABLE"    # Alias for UNAVAILABLE
    AUTH_ERROR = "AUTH_ERROR"              # Invalid API key (401/403)
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"    # Out of credits (402)
    RATE_LIMITED = "RATE_LIMITED"          # Rate limit exceeded (429)
    CANCELLED = "CANCELLED"                # Registration cancelled
    SUSPENDED = "SUSPENDED"                # Registration suspended
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"# Valid GSTIN registered to different entity


@dataclass
class GSTReturnRecord:
    """Represents a single GSTR return filing record."""
    return_type: str
    return_period: str
    filing_status: str
    filing_date: Optional[str] = None
    arn: Optional[str] = None

    @property
    def period(self) -> str:
        return self.return_period

    @property
    def status(self) -> str:
        return self.filing_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "return_type": self.return_type,
            "return_period": self.return_period,
            "filing_status": self.filing_status,
            "filing_date": self.filing_date,
            "arn": self.arn,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GSTReturnRecord":
        return cls(
            return_type=d.get("return_type", ""),
            return_period=d.get("return_period") or d.get("period") or "",
            filing_status=d.get("filing_status") or d.get("status") or "",
            filing_date=d.get("filing_date"),
            arn=d.get("arn"),
        )


@dataclass
class GSTFilingPreference:
    """Represents filing frequency preference (QRMP) for a quarter."""
    quarter: str
    preference: str

    def to_dict(self) -> Dict[str, Any]:
        return {"quarter": self.quarter, "preference": self.preference}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GSTFilingPreference":
        return cls(quarter=d.get("quarter", ""), preference=d.get("preference", ""))


@dataclass
class GSTComplianceSummary:
    """Summary of return filing compliance for a financial year."""
    total_filed: int
    gstr1_filed: int = 0
    gstr3b_filed: int = 0
    by_type: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_filed": self.total_filed,
            "gstr1_filed": self.gstr1_filed,
            "gstr3b_filed": self.gstr3b_filed,
            "by_type": self.by_type,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GSTComplianceSummary":
        by_type = d.get("by_type", {})
        gstr1 = d.get("gstr1_filed")
        if gstr1 is None and isinstance(by_type, dict):
            gstr1 = by_type.get("GSTR1", 0)
        gstr3b = d.get("gstr3b_filed")
        if gstr3b is None and isinstance(by_type, dict):
            gstr3b = by_type.get("GSTR3B", 0)
        return cls(
            total_filed=d.get("total_filed", 0),
            gstr1_filed=int(gstr1 or 0),
            gstr3b_filed=int(gstr3b or 0),
            by_type=by_type,
        )


@dataclass
class GSTTaxpayerData:
    """Normalized taxpayer registration record."""
    gstin: str
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    status: str = "Active"
    taxpayer_type: Optional[str] = None
    business_constitution: Optional[str] = None
    registration_date: Optional[str] = None
    cancellation_date: Optional[str] = None
    state_code: Optional[str] = None
    state_jurisdiction: Optional[str] = None
    state_jurisdiction_code: Optional[str] = None
    centre_jurisdiction: Optional[str] = None
    centre_jurisdiction_code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    address_details: Optional[Dict[str, Any]] = None
    nature_of_business: Optional[Any] = None
    block_status: Optional[str] = None
    einvoice_status: Optional[str] = None
    additional_addresses: List[Dict[str, Any]] = dc_field(default_factory=list)
    last_updated: Optional[str] = None
    profile_complete: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gstin": self.gstin,
            "legal_name": self.legal_name,
            "trade_name": self.trade_name,
            "status": self.status,
            "taxpayer_type": self.taxpayer_type,
            "business_constitution": self.business_constitution,
            "registration_date": self.registration_date,
            "cancellation_date": self.cancellation_date,
            "state_code": self.state_code,
            "state_jurisdiction": self.state_jurisdiction,
            "state_jurisdiction_code": self.state_jurisdiction_code,
            "centre_jurisdiction": self.centre_jurisdiction,
            "centre_jurisdiction_code": self.centre_jurisdiction_code,
            "address": self.address,
            "city": self.city,
            "pincode": self.pincode,
            "address_details": self.address_details,
            "nature_of_business": self.nature_of_business,
            "block_status": self.block_status,
            "einvoice_status": self.einvoice_status,
            "additional_addresses": self.additional_addresses,
            "last_updated": self.last_updated,
            "profile_complete": self.profile_complete,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any], profile_complete: bool = False) -> "GSTTaxpayerData":
        return cls(
            gstin=d.get("gstin", ""),
            legal_name=d.get("legal_name"),
            trade_name=d.get("trade_name"),
            status=d.get("status", "Active"),
            taxpayer_type=d.get("taxpayer_type"),
            business_constitution=d.get("business_constitution"),
            registration_date=d.get("registration_date"),
            cancellation_date=d.get("cancellation_date"),
            state_code=d.get("state_code"),
            state_jurisdiction=d.get("state_jurisdiction"),
            state_jurisdiction_code=d.get("state_jurisdiction_code"),
            centre_jurisdiction=d.get("centre_jurisdiction"),
            centre_jurisdiction_code=d.get("centre_jurisdiction_code"),
            address=d.get("address"),
            city=d.get("city"),
            pincode=d.get("pincode"),
            address_details=d.get("address_details"),
            nature_of_business=d.get("nature_of_business"),
            block_status=d.get("block_status"),
            einvoice_status=d.get("einvoice_status"),
            additional_addresses=d.get("additional_addresses", []),
            last_updated=d.get("last_updated"),
            profile_complete=profile_complete,
        )


@dataclass
class GSTVerificationRequest:
    """Request parameters for GST verification pipeline."""
    gstin: str
    expected_legal_name: Optional[str] = None
    include_profile: bool = True
    check_returns: bool = False
    financial_year: Optional[str] = None
    bid_id: Optional[str] = None
    convert_to_bidder_fact: bool = False

    def clean_gstin(self) -> str:
        return self.gstin.strip().upper() if self.gstin else ""


@dataclass
class GSTVerificationResponse:
    """Complete outcome of GSTIN verification and optional returns audit."""
    gstin: str
    status: GSTVerificationStatus
    http_status: int
    txn_id: str = dc_field(default_factory=lambda: str(uuid.uuid4()))
    data: Optional[GSTTaxpayerData] = None
    returns: List[GSTReturnRecord] = dc_field(default_factory=list)
    filing_preference: List[GSTFilingPreference] = dc_field(default_factory=list)
    compliance: Optional[GSTComplianceSummary] = None
    fy: Optional[str] = None
    credits_remaining: Optional[int] = None
    response_ms: float = 0.0
    response_hash: str = ""
    is_live: bool = True
    is_test: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "gstin": self.gstin,
            "status": self.status.value,
            "http_status": self.http_status,
            "data": self.data.to_dict() if self.data else None,
            "returns": [r.to_dict() for r in self.returns],
            "filing_preference": [p.to_dict() for p in self.filing_preference],
            "compliance": self.compliance.to_dict() if self.compliance else None,
            "fy": self.fy,
            "credits_remaining": self.credits_remaining,
            "response_ms": self.response_ms,
            "response_hash": self.response_hash,
            "is_live": self.is_live,
            "is_test": self.is_test,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }
