# -*- coding: utf-8 -*-
"""
Structured Pending Requirements Engine.
Phase 4: Explicit Identification of Missing, Incomplete, and Deficient Requirements.

Answers the authoritative question:
"What exactly is still missing from this bidder?"

Provides structured, actionable, and auditable pending items for the procurement officer.
"""

from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

from .applicability import ApplicabilityEvaluator, ApplicabilityStatus
from .models import BidderFact, ComplianceStatus, TenderRequirement, VerificationResult
from backend.verification.models import AdapterResponse


@dataclass
class PendingRequirement:
    requirement_id: str
    description: str
    category: str
    mandatory: bool
    applicability: str                     # APPLICABLE, NOT_APPLICABLE, UNKNOWN_REVIEW
    evidence_expected: str
    evidence_found: Optional[str]
    government_verification_expected: Optional[str]
    government_verification_result: Optional[str]
    compliance_result: str                 # MISSING, FAIL, REVIEW, PARTIAL, NOT_VERIFIED
    reason: str
    requires_human_review: bool
    deficiency_type: str                   # MISSING_DOCUMENT, DEFICIENT_VALUE, UNVERIFIED_GOVERNMENT, CONTRADICTION
    suggested_bidder_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "category": self.category,
            "mandatory": self.mandatory,
            "applicability": self.applicability,
            "evidence_expected": self.evidence_expected,
            "evidence_found": self.evidence_found,
            "government_verification_expected": self.government_verification_expected,
            "government_verification_result": self.government_verification_result,
            "compliance_result": self.compliance_result,
            "reason": self.reason,
            "requires_human_review": self.requires_human_review,
            "deficiency_type": self.deficiency_type,
            "suggested_bidder_action": self.suggested_bidder_action,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingRequirement":
        return cls(**data)


class PendingRequirementExtractor:
    """
    Extracts structured pending requirements from compliance results and government verification.
    """

    @staticmethod
    def extract_pending_requirements(
        requirements: List[TenderRequirement],
        compliance_results: List[VerificationResult],
        facts: List[BidderFact],
        government_responses: Optional[List[AdapterResponse]] = None,
        tender_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[PendingRequirement]:
        """
        Analyzes all requirements and compliance outcomes to determine pending items.
        Filters out non-applicable requirements.
        """
        gov_resps = government_responses or []
        gov_by_id: Dict[str, AdapterResponse] = {}
        for g in gov_resps:
            gov_by_id[g.adapter_name.lower()] = g
            if getattr(g, "queried_identifier", None):
                gov_by_id[str(g.queried_identifier).lower()] = g

        results_by_req: Dict[str, VerificationResult] = {r.requirement_id: r for r in compliance_results}
        facts_by_field: Dict[str, BidderFact] = {f.field.lower(): f for f in facts if f.field}
        for f in facts:
            if f.canonical_field:
                facts_by_field[f.canonical_field.lower()] = f

        pending_items: List[PendingRequirement] = []

        for req in requirements:
            # 1. Applicability Check
            app_res = ApplicabilityEvaluator.evaluate_applicability(req, facts, tender_metadata)
            if app_res.status == ApplicabilityStatus.NOT_APPLICABLE:
                continue

            v_res = results_by_req.get(req.requirement_id)
            if not v_res:
                continue

            status = v_res.status.upper() if isinstance(v_res.status, str) else v_res.status.value

            # If passed and not in review/missing, not pending
            if status == ComplianceStatus.PASS.value and not v_res.requires_human_review:
                continue

            # Check if this requirement maps to a government registry check
            req_field = (req.field or "").lower()
            gov_expected = None
            gov_result = None

            if "pan" in req_field or "pan" in req.category.lower():
                gov_expected = "API_SETU_PAN_VERIFICATION"
            elif "udyam" in req_field or "msme" in req_field:
                gov_expected = "API_SETU_UDYAM_VERIFICATION"
            elif "epfo" in req_field or "uan" in req_field:
                gov_expected = "API_SETU_EPFO_VERIFICATION"
            elif "esic" in req_field or "ip_number" in req_field:
                gov_expected = "API_SETU_ESIC_VERIFICATION"
            elif "dpiit" in req_field or "startup" in req_field:
                gov_expected = "API_SETU_DPIIT_VERIFICATION"
            elif "debarment" in req_field or "blacklist" in req_field:
                gov_expected = "DEBARMENT_REGISTRY_CHECK"

            if gov_expected:
                for g in gov_resps:
                    if (gov_expected.lower() in g.adapter_name.lower() or
                        g.adapter_name.lower() in gov_expected.lower()):
                        status_str = g.status.value if hasattr(g.status, "value") else str(g.status)
                        gov_result = f"{g.adapter_name}: {status_str}"
                        break

            # Categorize deficiency
            if status == ComplianceStatus.MISSING.value:
                def_type = "MISSING_DOCUMENT"
                action = f"Submit official document/certificate proving '{req.description}'."
            elif status == ComplianceStatus.FAIL.value:
                def_type = "DEFICIENT_VALUE"
                action = f"Submitted value '{v_res.actual}' fails required '{v_res.expected}'. Clarify or provide compliant evidence."
            elif gov_result and ("NOT_FOUND" in gov_result or "NOT_VERIFIED" in gov_result or "UNAVAILABLE" in gov_result):
                def_type = "UNVERIFIED_GOVERNMENT"
                action = f"Verify registration details with government portal ({gov_expected})."
            else:
                def_type = "AMBIGUOUS_EVIDENCE"
                action = "Procurement officer review required to inspect submitted clause or certificate."

            evidence_expected_str = f"{req.operator} {req.expected_value} {req.unit or ''}".strip()
            if not req.expected_value:
                evidence_expected_str = f"Proof of {req.description}"

            evidence_found_str = str(v_res.actual) if v_res.actual else None

            pending_items.append(PendingRequirement(
                requirement_id=req.requirement_id,
                description=req.description,
                category=req.category,
                mandatory=req.mandatory,
                applicability=app_res.status.value,
                evidence_expected=evidence_expected_str,
                evidence_found=evidence_found_str,
                government_verification_expected=gov_expected,
                government_verification_result=gov_result,
                compliance_result=status,
                reason=v_res.reason or "Requirement requires resolution or review.",
                requires_human_review=v_res.requires_human_review or (status != ComplianceStatus.PASS.value),
                deficiency_type=def_type,
                suggested_bidder_action=action,
            ))

        return pending_items
