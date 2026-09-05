# -*- coding: utf-8 -*-
"""
Deterministic Canonical Field Ontology & Synonym Resolver.

Architectural Principle:
    safe normalization > aggressive matching
    unmapped/ambiguous > false equivalence

The ontology normalizes concept identity prior to Step 4 rule evaluation
and Step 5 contradiction grouping. It NEVER makes compliance decisions,
strictly preserves raw field provenance, and deterministically refuses
ambiguous mappings.
"""

import re
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNMAPPED = "UNMAPPED"
    AMBIGUOUS = "AMBIGUOUS"


class ResolutionMethod(str, Enum):
    EXACT_CANONICAL = "EXACT_CANONICAL"
    EXACT_ALIAS = "EXACT_ALIAS"
    NORMALIZED_ALIAS = "NORMALIZED_ALIAS"


class CanonicalCategory(str, Enum):
    FINANCIAL = "FINANCIAL"
    REGULATORY_IDENTITY = "REGULATORY_IDENTITY"
    TECHNICAL_SPEC = "TECHNICAL_SPEC"
    ELIGIBILITY = "ELIGIBILITY"
    OPERATIONAL = "OPERATIONAL"
    COMPLIANCE_CERT = "COMPLIANCE_CERT"


@dataclass(frozen=True)
class CanonicalField:
    """Represents a canonical field definition in the GeM procurement ontology."""
    canonical_id: str
    label: str
    category: str
    aliases: List[str]
    normalization_type: str
    contradiction_eligible: bool
    family: Optional[str] = None
    description: Optional[str] = None


@dataclass
class CanonicalFieldResult:
    """Detailed traceable outcome of resolving a raw field string."""
    raw_field: str
    canonical_field_id: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    resolution_method: Optional[str] = None
    resolution_status: str = ResolutionStatus.UNMAPPED.value
    contradiction_eligible: bool = False
    family: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_field": self.raw_field,
            "canonical_field_id": self.canonical_field_id,
            "label": self.label,
            "category": self.category,
            "resolution_method": self.resolution_method,
            "resolution_status": self.resolution_status,
            "contradiction_eligible": self.contradiction_eligible,
            "family": self.family,
        }


def normalize_field_key(key: Optional[str]) -> str:
    """
    Deterministically normalizes a candidate field string:
    1. Lowers case and strips leading/trailing whitespace.
    2. Converts dashes, slashes, and whitespace sequences to single underscores.
    3. Strips all characters except a-z, 0-9, and underscore.
    4. Collapses multiple underscores and strips outer underscores.
    """
    if not key:
        return ""
    cleaned = str(key).strip().lower()
    # Replace separators with underscore
    cleaned = re.sub(r"[\s\-\/\.\:]+", "_", cleaned)
    # Remove non-alphanumeric/underscore
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


# High-risk collision keys that MUST be rejected as AMBIGUOUS
AMBIGUOUS_KEYS: Set[str] = {
    "experience",          # Ambiguous: could be duration in years or number of completed contracts
    "certificate",         # Ambiguous: could be ISO, OEM, MSE, Startup, etc.
    "certification",       # Ambiguous: generic certification
    "financials",          # Ambiguous: could be turnover, net worth, profit
    "financial_capacity",  # Ambiguous: generic financial bucket
    "validity",            # Ambiguous: bid validity vs warranty vs certificate validity
    "security",            # Ambiguous: EMD vs ePBG vs security deposit
    "deposit",             # Ambiguous: EMD vs general deposit
    "turnover_ratio",      # Ambiguous: ratio vs absolute currency value
    "financial_ratio",     # Ambiguous: ratio vs absolute figure
}

# Pre-normalized ambiguous keys
_AMBIGUOUS_NORMALIZED: Set[str] = {normalize_field_key(k) for k in AMBIGUOUS_KEYS}


# Registry of Canonical Fields
CANONICAL_FIELDS: List[CanonicalField] = [
    # --- 1. FINANCIAL ---
    CanonicalField(
        canonical_id="ANNUAL_TURNOVER",
        label="Annual Turnover",
        category=CanonicalCategory.FINANCIAL.value,
        family="TURNOVER",
        normalization_type="CURRENCY_CR",
        contradiction_eligible=True,
        aliases=[
            "annual_turnover",
            "turnover_cr",
            "turnover_amount",
            "bidder_turnover_lakh",
            "turnover_inr",
            "yearly_turnover",
            "annual_turnover_inr",
            "turnover",
            "annual_revenue",
            "firm_turnover",
            "revenue",
        ],
        description="Single-year or general turnover figures declared by the bidder.",
    ),
    CanonicalField(
        canonical_id="AVERAGE_ANNUAL_TURNOVER",
        label="Average Annual Turnover",
        category=CanonicalCategory.FINANCIAL.value,
        family="TURNOVER",
        normalization_type="CURRENCY_CR",
        contradiction_eligible=True,
        aliases=[
            "average_annual_turnover",
            "avg_annual_turnover",
            "average_turnover_3_years",
            "3_year_average_turnover",
            "three_year_average_turnover",
            "aat",
        ],
        description="Multi-year (typically 3-year) average annual turnover certified by CA. Distinct from single-year turnover.",
    ),
    CanonicalField(
        canonical_id="NET_WORTH",
        label="Net Worth",
        category=CanonicalCategory.FINANCIAL.value,
        family="NET_WORTH",
        normalization_type="CURRENCY_CR",
        contradiction_eligible=True,
        aliases=[
            "net_worth_cr",
            "net_worth",
            "bidder_net_worth",
            "net_worth_amount",
            "networth",
            "networth_cr",
        ],
        description="Net worth of the bidder as per audited balance sheet.",
    ),
    CanonicalField(
        canonical_id="EMD_REQUIREMENT",
        label="EMD Requirement",
        category=CanonicalCategory.FINANCIAL.value,
        family="EMD",
        normalization_type="BOOLEAN",
        contradiction_eligible=False,
        aliases=[
            "emd_required",
            "emd_exemption",
            "earnest_money_deposit_required",
            "emd_mandatory",
        ],
        description="Requirement flag or exemption status for Earnest Money Deposit.",
    ),
    CanonicalField(
        canonical_id="EMD_AMOUNT",
        label="EMD Amount",
        category=CanonicalCategory.FINANCIAL.value,
        family="EMD",
        normalization_type="CURRENCY_INR",
        contradiction_eligible=True,
        aliases=[
            "emd_amount",
            "emd_amount_inr",
            "earnest_money_amount",
            "emd_value",
        ],
        description="Specific monetary amount required for Earnest Money Deposit.",
    ),
    CanonicalField(
        canonical_id="EPBG_PERCENTAGE",
        label="ePBG Percentage",
        category=CanonicalCategory.FINANCIAL.value,
        family="EPBG",
        normalization_type="PERCENT",
        contradiction_eligible=True,
        aliases=[
            "epbg_percentage",
            "epbg_percent",
            "epbg",
            "performance_bank_guarantee_percent",
            "pbg_percentage",
            "pb_guarantee_percentage",
        ],
        description="Performance Bank Guarantee rate expressed as a percentage of contract value.",
    ),
    CanonicalField(
        canonical_id="EPBG_AMOUNT",
        label="ePBG Amount",
        category=CanonicalCategory.FINANCIAL.value,
        family="EPBG",
        normalization_type="CURRENCY_INR",
        contradiction_eligible=True,
        aliases=[
            "epbg_amount",
            "pbg_amount",
            "performance_guarantee_amount",
        ],
        description="Fixed monetary amount required for Performance Bank Guarantee.",
    ),

    # --- 2. REGULATORY & ENTITY IDENTITY ---
    CanonicalField(
        canonical_id="GSTIN",
        label="Goods and Services Tax Identification Number (GSTIN)",
        category=CanonicalCategory.REGULATORY_IDENTITY.value,
        family="GSTIN",
        normalization_type="REGEX_ID",
        contradiction_eligible=True,
        aliases=[
            "gstin",
            "gst_number",
            "gst_in",
            "gstin_number",
            "gst",
        ],
        description="15-character statutory GST identification number.",
    ),
    CanonicalField(
        canonical_id="PAN",
        label="Permanent Account Number (PAN)",
        category=CanonicalCategory.REGULATORY_IDENTITY.value,
        family="PAN",
        normalization_type="REGEX_ID",
        contradiction_eligible=True,
        aliases=[
            "pan",
            "pan_number",
            "company_pan",
            "bidder_pan",
            "pan_card",
        ],
        description="10-character statutory PAN issued by Income Tax Department.",
    ),
    CanonicalField(
        canonical_id="UDYAM_REGISTRATION",
        label="Udyam Registration Number",
        category=CanonicalCategory.REGULATORY_IDENTITY.value,
        family="UDYAM",
        normalization_type="REGEX_ID",
        contradiction_eligible=True,
        aliases=[
            "udyam",
            "udyam_number",
            "udyam_registration",
            "udyam_reg_number",
            "msme_registration_number",
            "msme_number",
            "udyam_registration_number",
            "msme_reg_no",
        ],
        description="Statutory MSME registration number issued by Ministry of MSME.",
    ),
    CanonicalField(
        canonical_id="LEGAL_ENTITY_NAME",
        label="Legal Entity Name",
        category=CanonicalCategory.REGULATORY_IDENTITY.value,
        family="LEGAL_ENTITY_NAME",
        normalization_type="STRING",
        contradiction_eligible=True,
        aliases=[
            "company_name",
            "legal_name",
            "entity_name",
            "bidder_name",
            "firm_name",
            "vendor_name",
            "contractor_name",
        ],
        description="Official registered business entity or company name.",
    ),
    CanonicalField(
        canonical_id="IS_MSE",
        label="Micro & Small Enterprise (MSE) Status",
        category=CanonicalCategory.REGULATORY_IDENTITY.value,
        family="STATUTORY_EXEMPTION",
        normalization_type="BOOLEAN",
        contradiction_eligible=True,
        aliases=[
            "is_mse",
            "mse_registered",
            "msme_status",
            "is_msme",
            "mse_status",
        ],
        description="MSE statutory eligibility indicator for preferential evaluation.",
    ),
    CanonicalField(
        canonical_id="IS_STARTUP",
        label="DPIIT Recognized Startup Status",
        category=CanonicalCategory.REGULATORY_IDENTITY.value,
        family="STATUTORY_EXEMPTION",
        normalization_type="BOOLEAN",
        contradiction_eligible=True,
        aliases=[
            "is_startup",
            "startup_recognized",
            "dpiit_recognized",
            "startup_status",
            "is_dpiit_startup",
        ],
        description="DPIIT startup statutory eligibility indicator.",
    ),

    # --- 3. TECHNICAL & OPERATIONAL SPECIFICATIONS ---
    CanonicalField(
        canonical_id="WARRANTY_DURATION",
        label="Warranty Duration",
        category=CanonicalCategory.TECHNICAL_SPEC.value,
        family="WARRANTY",
        normalization_type="MONTHS",
        contradiction_eligible=True,
        aliases=[
            "warranty_years",
            "warranty",
            "warranty_duration",
            "warranty_months",
            "warranty_period",
            "warranty_term",
        ],
        description="Declared warranty or operational maintenance support duration.",
    ),
    CanonicalField(
        canonical_id="DELIVERY_PERIOD",
        label="Delivery Period",
        category=CanonicalCategory.OPERATIONAL.value,
        family="DELIVERY",
        normalization_type="DAYS",
        contradiction_eligible=True,
        aliases=[
            "delivery_days",
            "delivery_period",
            "delivery_time",
            "lead_time_days",
            "delivery_timeline",
            "delivery_schedule_days",
        ],
        description="Contract delivery schedule or lead time in days.",
    ),
    CanonicalField(
        canonical_id="LOCAL_CONTENT_PERCENT",
        label="Local Content Percentage (Make in India)",
        category=CanonicalCategory.ELIGIBILITY.value,
        family="LOCAL_CONTENT",
        normalization_type="PERCENT",
        contradiction_eligible=True,
        aliases=[
            "local_content_percent",
            "local_content_percentage",
            "mii_local_content",
            "class_1_local_content",
            "local_content_declared",
        ],
        description="Percentage of domestic value addition declared under Public Procurement Order.",
    ),
    CanonicalField(
        canonical_id="ISO_CERTIFICATION",
        label="ISO Quality Management Certification",
        category=CanonicalCategory.COMPLIANCE_CERT.value,
        family="CERTIFICATION",
        normalization_type="BOOLEAN",
        contradiction_eligible=True,
        aliases=[
            "iso_cert",
            "iso_certification",
            "iso_9001_cert",
            "iso_9001",
            "iso_9001_certification",
            "iso_14001_cert",
        ],
        description="ISO standard quality management certification compliance.",
    ),
    CanonicalField(
        canonical_id="LOCAL_SUPPORT",
        label="Local Service Support / Center Availability",
        category=CanonicalCategory.OPERATIONAL.value,
        family="LOCAL_SUPPORT",
        normalization_type="BOOLEAN",
        contradiction_eligible=True,
        aliases=[
            "local_support",
            "local_service_support",
            "service_center_available",
            "local_service_centers",
        ],
        description="Availability of authorized local service stations or regional support hubs.",
    ),
    CanonicalField(
        canonical_id="OEM_AUTHORIZATION",
        label="OEM Authorization Letter (MAF)",
        category=CanonicalCategory.ELIGIBILITY.value,
        family="OEM_AUTHORIZATION",
        normalization_type="BOOLEAN",
        contradiction_eligible=True,
        aliases=[
            "oem_authorization",
            "authorized_distributor",
            "oem_authorization_letter",
            "maf_submitted",
            "manufacturer_authorization",
        ],
        description="Original Equipment Manufacturer authorization certificate.",
    ),
    CanonicalField(
        canonical_id="BID_VALIDITY_DAYS",
        label="Bid Validity Period",
        category=CanonicalCategory.OPERATIONAL.value,
        family="BID_VALIDITY",
        normalization_type="DAYS",
        contradiction_eligible=True,
        aliases=[
            "bid_validity_days",
            "bid_validity",
            "offer_validity_days",
            "tender_validity_days",
        ],
        description="Number of days the submitted commercial and technical offer remains binding.",
    ),

    # --- 4. EXPERIENCE FAMILIES (DISTINCT TO PREVENT COLLISION) ---
    CanonicalField(
        canonical_id="PAST_EXPERIENCE_DURATION",
        label="Past Experience Duration (Years)",
        category=CanonicalCategory.ELIGIBILITY.value,
        family="EXPERIENCE",
        normalization_type="YEARS",
        contradiction_eligible=True,
        aliases=[
            "experience_years",
            "years_of_experience",
            "past_experience_years",
            "industry_experience_years",
        ],
        description="Temporal duration of vendor experience in the relevant commercial domain.",
    ),
    CanonicalField(
        canonical_id="SIMILAR_PROJECTS_COUNT",
        label="Similar Completed Projects Count",
        category=CanonicalCategory.ELIGIBILITY.value,
        family="EXPERIENCE",
        normalization_type="COUNT",
        contradiction_eligible=True,
        aliases=[
            "similar_projects",
            "similar_contracts_completed",
            "completed_projects_count",
            "past_project_count",
        ],
        description="Integer count of completed past contracts of similar technical scope.",
    ),
]


# Fast O(1) in-memory indices
_EXACT_INDEX: Dict[str, Tuple[CanonicalField, str]] = {}
_NORMALIZED_INDEX: Dict[str, CanonicalField] = {}

for _cf in CANONICAL_FIELDS:
    # 1. Exact canonical ID
    _EXACT_INDEX[_cf.canonical_id] = (_cf, ResolutionMethod.EXACT_CANONICAL.value)
    # Also index normalized canonical ID
    _norm_cid = normalize_field_key(_cf.canonical_id)
    if _norm_cid not in _NORMALIZED_INDEX:
        _NORMALIZED_INDEX[_norm_cid] = _cf

    # 2. Aliases
    for _alias in _cf.aliases:
        _EXACT_INDEX[_alias] = (_cf, ResolutionMethod.EXACT_ALIAS.value)
        _norm_alias = normalize_field_key(_alias)
        if _norm_alias not in _NORMALIZED_INDEX:
            _NORMALIZED_INDEX[_norm_alias] = _cf


def resolve_field(raw_field: Optional[str]) -> CanonicalFieldResult:
    """
    Pure deterministic resolution of raw field string to CanonicalFieldResult.
    O(1) execution time, zero external network calls, zero LLMs.

    Resolution Priority:
    1. Empty/None -> UNMAPPED
    2. Explicit ambiguous check -> AMBIGUOUS
    3. Exact match against canonical_id or alias -> RESOLVED (EXACT_CANONICAL / EXACT_ALIAS)
    4. Normalized key match -> RESOLVED (NORMALIZED_ALIAS)
    5. Fallback -> UNMAPPED
    """
    if raw_field is None:
        return CanonicalFieldResult(
            raw_field="",
            resolution_status=ResolutionStatus.UNMAPPED.value,
        )

    raw_str = str(raw_field).strip()
    if not raw_str:
        return CanonicalFieldResult(
            raw_field=raw_str,
            resolution_status=ResolutionStatus.UNMAPPED.value,
        )

    # 1. Ambiguity Guard
    norm_key = normalize_field_key(raw_str)
    if norm_key in _AMBIGUOUS_NORMALIZED:
        return CanonicalFieldResult(
            raw_field=raw_str,
            canonical_field_id=None,
            label=None,
            category=None,
            resolution_method=None,
            resolution_status=ResolutionStatus.AMBIGUOUS.value,
            contradiction_eligible=False,
            family=None,
        )

    # 2. Exact match check
    if raw_str in _EXACT_INDEX:
        cf, method = _EXACT_INDEX[raw_str]
        return CanonicalFieldResult(
            raw_field=raw_str,
            canonical_field_id=cf.canonical_id,
            label=cf.label,
            category=cf.category,
            resolution_method=method,
            resolution_status=ResolutionStatus.RESOLVED.value,
            contradiction_eligible=cf.contradiction_eligible,
            family=cf.family,
        )

    # 3. Normalized alias check
    if norm_key in _NORMALIZED_INDEX:
        cf = _NORMALIZED_INDEX[norm_key]
        return CanonicalFieldResult(
            raw_field=raw_str,
            canonical_field_id=cf.canonical_id,
            label=cf.label,
            category=cf.category,
            resolution_method=ResolutionMethod.NORMALIZED_ALIAS.value,
            resolution_status=ResolutionStatus.RESOLVED.value,
            contradiction_eligible=cf.contradiction_eligible,
            family=cf.family,
        )

    # 4. Deterministic UNMAPPED
    return CanonicalFieldResult(
        raw_field=raw_str,
        canonical_field_id=None,
        label=None,
        category=None,
        resolution_method=None,
        resolution_status=ResolutionStatus.UNMAPPED.value,
        contradiction_eligible=False,
        family=None,
    )


def get_canonical_field(canonical_id: str) -> Optional[CanonicalField]:
    """Retrieve CanonicalField definition by canonical ID."""
    entry = _EXACT_INDEX.get(canonical_id)
    return entry[0] if entry else None


def list_canonical_fields() -> List[CanonicalField]:
    """List all registered canonical fields in the ontology."""
    return list(CANONICAL_FIELDS)
