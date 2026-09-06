# -*- coding: utf-8 -*-
"""
Deterministic Requirement Applicability Engine.
Phase 3: Authoritative Statutory & Tender-Specific Applicability Resolution.

Ensures bidders are evaluated ONLY against requirements that genuinely apply to them.
A bidder is never penalized (via score deductions or compliance failure) for a
statutory or tender clause that is demonstrably NOT_APPLICABLE.

All applicability resolutions are deterministic, explainable, and fully auditable.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import BidderFact, ComplianceStatus, TenderRequirement


class ApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN_REVIEW = "UNKNOWN_REVIEW"


@dataclass(frozen=True)
class ApplicabilityResolution:
    requirement_id: str
    status: ApplicabilityStatus
    reason: str
    applicability_rule: str
    supporting_evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "status": self.status.value,
            "reason": self.reason,
            "applicability_rule": self.applicability_rule,
            "supporting_evidence": self.supporting_evidence or {},
        }


class ApplicabilityEvaluator:
    """
    Pure deterministic evaluator for tender requirement applicability.
    Zero LLM calls, zero network calls.
    """

    @staticmethod
    def evaluate_applicability(
        requirement: TenderRequirement,
        facts: List[BidderFact],
        tender_metadata: Optional[Dict[str, Any]] = None,
    ) -> ApplicabilityResolution:
        """
        Determines whether a tender requirement is APPLICABLE, NOT_APPLICABLE,
        or UNKNOWN_REVIEW for a given bidder and tender context.
        """
        tender_meta = tender_metadata or {}
        req_app = requirement.applicability or {}

        # 1. Superseded / Precedence Override
        if not requirement.is_effective:
            return ApplicabilityResolution(
                requirement_id=requirement.requirement_id,
                status=ApplicabilityStatus.NOT_APPLICABLE,
                reason=requirement.precedence_notes or "Requirement superseded by higher-priority clause.",
                applicability_rule="PRECEDENCE_SUPERSEDED",
            )

        # 2. Explicit rule in requirement applicability dictionary
        explicit_status = req_app.get("status")
        if explicit_status:
            status_str = str(explicit_status).upper().strip()
            if status_str == "NOT_APPLICABLE":
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=req_app.get("reason", "Marked not applicable in tender specification."),
                    applicability_rule="EXPLICIT_SPECIFICATION",
                )
            elif status_str in ("UNKNOWN", "UNKNOWN_REVIEW", "REVIEW"):
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.UNKNOWN_REVIEW,
                    reason=req_app.get("reason", "Applicability marked uncertain in tender specification; officer review required."),
                    applicability_rule="TENDER_SPECIFICATION_UNCERTAIN",
                )

        # Index facts for lookup
        facts_by_field: Dict[str, Any] = {}
        facts_by_canonical: Dict[str, Any] = {}
        for f in facts:
            if f.field:
                facts_by_field[f.field.lower().strip()] = f.value
            if f.canonical_field:
                facts_by_canonical[f.canonical_field.upper().strip()] = f.value

        # 3. Category / Procurement Scope Applicability
        tender_category = (tender_meta.get("category") or req_app.get("tender_category") or "").upper().strip()
        applicable_categories = [str(c).upper().strip() for c in req_app.get("applicable_categories", [])]
        if applicable_categories and tender_category and tender_category not in applicable_categories:
            return ApplicabilityResolution(
                requirement_id=requirement.requirement_id,
                status=ApplicabilityStatus.NOT_APPLICABLE,
                reason=f"Clause applies only to categories {applicable_categories}, tender category is '{tender_category}'.",
                applicability_rule="CATEGORY_EXCLUSION",
            )

        # 4. OEM Authorization Applicability
        # If requirement is OEM Authorization, but bidder IS the OEM / original manufacturer
        is_oem = facts_by_field.get("is_oem") or facts_by_canonical.get("IS_OEM")
        bidder_role = str(facts_by_field.get("bidder_role") or facts_by_canonical.get("BIDDER_ROLE", "")).upper().strip()
        if requirement.category == "OEM_AUTHORIZATION" or "oem_auth" in (requirement.field or "").lower():
            oem_fact = next((f for f in facts if f.field and f.field.lower() in ("is_oem", "bidder_role")), None)
            if oem_fact and getattr(oem_fact, "extraction_confidence", "") == "LOW":
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.UNKNOWN_REVIEW,
                    reason="Bidder claims OEM status, but evidence extraction confidence is LOW; officer review required.",
                    applicability_rule="OEM_STATUS_UNCERTAIN",
                    supporting_evidence={"bidder_role": bidder_role, "confidence": "LOW"},
                )
            if is_oem is True or bidder_role in ("OEM", "ORIGINAL_EQUIPMENT_MANUFACTURER", "MANUFACTURER"):
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason="Bidder is the Original Equipment Manufacturer (OEM); reseller OEM authorization is not applicable.",
                    applicability_rule="OEM_SELF_MANUFACTURER",
                    supporting_evidence={"is_oem": True, "bidder_role": bidder_role},
                )

        # 5. Bidder Type (OEM vs Reseller / Manufacturer vs Trader)
        applicable_roles = [str(r).upper().strip() for r in req_app.get("applicable_bidder_roles", [])]
        if applicable_roles:
            if not bidder_role:
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.UNKNOWN_REVIEW,
                    reason=f"Clause applies conditionally to roles {applicable_roles}, but bidder role is unstated or unverified in bid submission.",
                    applicability_rule="BIDDER_ROLE_UNVERIFIED",
                )
            elif bidder_role not in applicable_roles:
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=f"Clause applies only to roles {applicable_roles}, bidder is registered as '{bidder_role}'.",
                    applicability_rule="BIDDER_ROLE_EXCLUSION",
                )

        # 6. EPFO Statutory Exemption (Establishment Size)
        # EPFO Act applies to establishments with >= 20 employees
        if "epfo" in (requirement.field or "").lower() or requirement.category == "EPFO_COMPLIANCE":
            emp_count = facts_by_field.get("employee_count") or facts_by_canonical.get("EMPLOYEE_COUNT")
            if emp_count is not None:
                try:
                    num_emp = int(emp_count)
                    if num_emp < 20 and not req_app.get("mandate_for_all_sizes"):
                        emp_fact = next((f for f in facts if f.field and f.field.lower() == "employee_count"), None)
                        if emp_fact and getattr(emp_fact, "extraction_confidence", "") == "LOW":
                            return ApplicabilityResolution(
                                requirement_id=requirement.requirement_id,
                                status=ApplicabilityStatus.UNKNOWN_REVIEW,
                                reason=f"Bidder declares {num_emp} employees for EPF exemption, but extraction confidence is LOW; officer review required.",
                                applicability_rule="STATUTORY_THRESHOLD_UNVERIFIED",
                                supporting_evidence={"employee_count": num_emp},
                            )
                        return ApplicabilityResolution(
                            requirement_id=requirement.requirement_id,
                            status=ApplicabilityStatus.NOT_APPLICABLE,
                            reason=f"Statutory EPF Act applies to establishments with 20+ employees; bidder has {num_emp} employees.",
                            applicability_rule="STATUTORY_THRESHOLD_EPFO",
                            supporting_evidence={"employee_count": num_emp},
                        )
                except (ValueError, TypeError):
                    return ApplicabilityResolution(
                        requirement_id=requirement.requirement_id,
                        status=ApplicabilityStatus.UNKNOWN_REVIEW,
                        reason=f"Submitted employee count '{emp_count}' cannot be deterministically validated; officer review required.",
                        applicability_rule="STATUTORY_THRESHOLD_UNVERIFIED",
                    )

        # 7. ESIC Statutory Exemption (Establishment Size / Area)
        # ESIC applies to establishments with >= 10 employees
        if "esic" in (requirement.field or "").lower() or requirement.category == "ESIC_COMPLIANCE":
            emp_count = facts_by_field.get("employee_count") or facts_by_canonical.get("EMPLOYEE_COUNT")
            if emp_count is not None:
                try:
                    num_emp = int(emp_count)
                    if num_emp < 10 and not req_app.get("mandate_for_all_sizes"):
                        emp_fact = next((f for f in facts if f.field and f.field.lower() == "employee_count"), None)
                        if emp_fact and getattr(emp_fact, "extraction_confidence", "") == "LOW":
                            return ApplicabilityResolution(
                                requirement_id=requirement.requirement_id,
                                status=ApplicabilityStatus.UNKNOWN_REVIEW,
                                reason=f"Bidder declares {num_emp} employees for ESIC exemption, but extraction confidence is LOW; officer review required.",
                                applicability_rule="STATUTORY_THRESHOLD_UNVERIFIED",
                                supporting_evidence={"employee_count": num_emp},
                            )
                        return ApplicabilityResolution(
                            requirement_id=requirement.requirement_id,
                            status=ApplicabilityStatus.NOT_APPLICABLE,
                            reason=f"Statutory ESIC Act applies to establishments with 10+ employees; bidder has {num_emp} employees.",
                            applicability_rule="STATUTORY_THRESHOLD_ESIC",
                            supporting_evidence={"employee_count": num_emp},
                        )
                except (ValueError, TypeError):
                    return ApplicabilityResolution(
                        requirement_id=requirement.requirement_id,
                        status=ApplicabilityStatus.UNKNOWN_REVIEW,
                        reason=f"Submitted employee count '{emp_count}' for ESIC cannot be deterministically validated; officer review required.",
                        applicability_rule="STATUTORY_THRESHOLD_UNVERIFIED",
                    )

        # 8. Startup / MSE Statutory Exemptions (Turnover & Prior Experience)
        is_mse = facts_by_field.get("is_mse") or facts_by_canonical.get("IS_MSE")
        is_startup = facts_by_field.get("is_startup") or facts_by_canonical.get("IS_STARTUP")
        
        is_exp_or_turnover = any(
            t in (requirement.field or "").lower() or t in requirement.category.lower()
            for t in ("turnover", "experience", "past_performance", "annual_turnover")
        )

        if is_exp_or_turnover:
            if req_app.get("mse_exemption_allowed") and is_mse is True:
                mse_fact = next((f for f in facts if f.field and f.field.lower() in ("is_mse", "udyam_registration")), None)
                if mse_fact and getattr(mse_fact, "extraction_confidence", "") == "LOW":
                    return ApplicabilityResolution(
                        requirement_id=requirement.requirement_id,
                        status=ApplicabilityStatus.UNKNOWN_REVIEW,
                        reason=f"MSE exemption claimed for '{requirement.description}', but supporting evidence has LOW extraction confidence; officer review required.",
                        applicability_rule="EXEMPTION_EVIDENCE_AMBIGUOUS",
                        supporting_evidence={"is_mse": True, "confidence": "LOW"},
                    )
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=f"Statutory exemption: MSE verified under GeM Policy for '{requirement.description}'.",
                    applicability_rule="MSE_STATUTORY_EXEMPTION",
                    supporting_evidence={"is_mse": True},
                )
            if req_app.get("startup_exemption_allowed") and is_startup is True:
                startup_fact = next((f for f in facts if f.field and f.field.lower() in ("is_startup", "dpiit_recognized")), None)
                if startup_fact and getattr(startup_fact, "extraction_confidence", "") == "LOW":
                    return ApplicabilityResolution(
                        requirement_id=requirement.requirement_id,
                        status=ApplicabilityStatus.UNKNOWN_REVIEW,
                        reason=f"DPIIT Startup exemption claimed for '{requirement.description}', but evidence has LOW extraction confidence; officer review required.",
                        applicability_rule="EXEMPTION_EVIDENCE_AMBIGUOUS",
                        supporting_evidence={"is_startup": True, "confidence": "LOW"},
                    )
                return ApplicabilityResolution(
                    requirement_id=requirement.requirement_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=f"Statutory exemption: DPIIT recognized Startup under GeM Policy for '{requirement.description}'.",
                    applicability_rule="STARTUP_STATUTORY_EXEMPTION",
                    supporting_evidence={"is_startup": True},
                )

        # 9. Default: Requirement is APPLICABLE
        return ApplicabilityResolution(
            requirement_id=requirement.requirement_id,
            status=ApplicabilityStatus.APPLICABLE,
            reason="Requirement is active, within procurement scope, and fully applicable to bidder.",
            applicability_rule="STANDARD_APPLICABLE",
        )
