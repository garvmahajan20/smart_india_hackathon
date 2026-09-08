# -*- coding: utf-8 -*-
"""
Deterministic Compliance Scoring Engine.
Phase 6: Authoritative Numerical Compliance Scoring with Mandatory-Failure Capping.

Guarantees:
- Fully deterministic and reproducible (zero LLM / probabilistic components).
- Transparent, explainable breakdown of total, applicable, passed, failed, and missing clauses.
- Critical-Failure Invariant: High performance on minor/optional clauses NEVER conceals
  a statutory or mandatory requirement failure (enforced via hard score caps).
"""

from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

from .applicability import ApplicabilityEvaluator, ApplicabilityStatus
from .models import ComplianceStatus, Severity, TenderRequirement, VerificationResult
from backend.verification.models import IntegrityFinding


@dataclass
class ScoreDeduction:
    requirement_id: str
    description: str
    status: str
    severity: str
    deduction_points: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "status": self.status,
            "severity": self.severity,
            "deduction_points": round(self.deduction_points, 2),
            "reason": self.reason,
        }


@dataclass
class ComplianceScoreBreakdown:
    total_requirements: int
    total_applicable: int
    passed: int
    failed: int
    missing: int
    under_review: int
    not_verified: int
    not_applicable: int
    raw_score: float
    final_score: float
    is_capped: bool
    cap_reason: Optional[str] = None
    deductions: List[ScoreDeduction] = dc_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requirements": self.total_requirements,
            "total_applicable": self.total_applicable,
            "passed": self.passed,
            "failed": self.failed,
            "missing": self.missing,
            "under_review": self.under_review,
            "not_verified": self.not_verified,
            "not_applicable": self.not_applicable,
            "raw_score": round(self.raw_score, 2),
            "final_score": round(self.final_score, 2),
            "is_capped": self.is_capped,
            "cap_reason": self.cap_reason,
            "deductions": [d.to_dict() for d in self.deductions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComplianceScoreBreakdown":
        deductions = [ScoreDeduction(**d) for d in data.get("deductions", [])]
        d = dict(data)
        d["deductions"] = deductions
        return cls(**d)


class ComplianceScoringEngine:
    """
    Pure deterministic compliance scoring calculator.
    """

    MANDATORY_BASE_WEIGHT = 10.0
    OPTIONAL_BASE_WEIGHT = 4.0

    SEVERITY_MULTIPLIERS = {
        Severity.CRITICAL.value: 1.5,
        Severity.MAJOR.value: 1.0,
        Severity.MINOR.value: 0.6,
        Severity.INFO.value: 0.4,
    }

    # Hard Cap Boundaries
    MANDATORY_FAIL_CAP = 40.0
    MANDATORY_MISSING_CAP = 55.0
    CRITICAL_CONTRADICTION_CAP = 65.0
    DEBARMENT_SCORE = 0.0

    @classmethod
    def calculate_score(
        cls,
        requirements: List[TenderRequirement],
        compliance_results: List[VerificationResult],
        integrity_findings: Optional[List[IntegrityFinding]] = None,
        is_debarred: bool = False,
        facts: Optional[List[Any]] = None,
        tender_metadata: Optional[Dict[str, Any]] = None,
    ) -> ComplianceScoreBreakdown:
        """
        Calculates the definitive overall compliance score and audit breakdown.
        """
        findings = integrity_findings or []
        facts_list = facts or []
        results_by_req = {r.requirement_id: r for r in compliance_results}

        total_reqs = len(requirements)
        applicable_count = 0
        pass_count = 0
        fail_count = 0
        missing_count = 0
        review_count = 0
        not_verified_count = 0
        na_count = 0

        total_possible_points = 0.0
        total_earned_points = 0.0
        deductions: List[ScoreDeduction] = []

        has_mandatory_fail = False
        has_mandatory_missing = False

        for req in requirements:
            # 1. Applicability Resolution
            app_res = ApplicabilityEvaluator.evaluate_applicability(req, facts_list, tender_metadata)
            if app_res.status == ApplicabilityStatus.NOT_APPLICABLE:
                na_count += 1
                continue

            applicable_count += 1
            v_res = results_by_req.get(req.requirement_id)
            if not v_res:
                # No result -> treated as missing
                missing_count += 1
                has_mandatory_missing = has_mandatory_missing or req.mandatory
                continue

            status = v_res.status.upper() if isinstance(v_res.status, str) else v_res.status.value
            severity = v_res.severity.upper() if isinstance(v_res.severity, str) else v_res.severity.value

            # Weight calculation
            base_weight = cls.MANDATORY_BASE_WEIGHT if req.mandatory else cls.OPTIONAL_BASE_WEIGHT
            multiplier = cls.SEVERITY_MULTIPLIERS.get(severity, 1.0)
            req_weight = base_weight * multiplier
            total_possible_points += req_weight

            if status in (ComplianceStatus.PASS.value, "OVERRIDDEN_PASS"):
                if app_res.status == ApplicabilityStatus.UNKNOWN_REVIEW and status != "OVERRIDDEN_PASS":
                    review_count += 1
                    earned = req_weight * 0.50
                    total_earned_points += earned
                    deductions.append(ScoreDeduction(
                        requirement_id=req.requirement_id,
                        description=req.description,
                        status="UNKNOWN_REVIEW",
                        severity=severity,
                        deduction_points=req_weight - earned,
                        reason=f"Applicability uncertain ({app_res.reason}): subject to procurement officer review.",
                    ))
                else:
                    pass_count += 1
                    total_earned_points += req_weight

            elif status == ComplianceStatus.PARTIAL.value:
                review_count += 1
                earned = req_weight * 0.50
                total_earned_points += earned
                deductions.append(ScoreDeduction(
                    requirement_id=req.requirement_id,
                    description=req.description,
                    status=status,
                    severity=severity,
                    deduction_points=req_weight - earned,
                    reason=f"Partial compliance: {v_res.reason}",
                ))

            elif status == ComplianceStatus.REVIEW.value:
                review_count += 1
                earned = req_weight * 0.25
                total_earned_points += earned
                deductions.append(ScoreDeduction(
                    requirement_id=req.requirement_id,
                    description=req.description,
                    status=status,
                    severity=severity,
                    deduction_points=req_weight - earned,
                    reason=f"Under human review: {v_res.reason}",
                ))

            elif status in ("NOT_VERIFIED", "UNAVAILABLE"):
                not_verified_count += 1
                deductions.append(ScoreDeduction(
                    requirement_id=req.requirement_id,
                    description=req.description,
                    status=status,
                    severity=severity,
                    deduction_points=req_weight,
                    reason=f"Government registry verification unresolved: {v_res.reason}",
                ))

            elif status == ComplianceStatus.MISSING.value:
                missing_count += 1
                if req.mandatory:
                    has_mandatory_missing = True
                deductions.append(ScoreDeduction(
                    requirement_id=req.requirement_id,
                    description=req.description,
                    status=status,
                    severity=severity,
                    deduction_points=req_weight,
                    reason=f"Required evidence missing: {v_res.reason}",
                ))

            elif status in (ComplianceStatus.FAIL.value, "OVERRIDDEN_FAIL"):
                fail_count += 1
                if req.mandatory:
                    has_mandatory_fail = True
                deductions.append(ScoreDeduction(
                    requirement_id=req.requirement_id,
                    description=req.description,
                    status=status,
                    severity=severity,
                    deduction_points=req_weight,
                    reason=f"Requirement failed: {v_res.reason}",
                ))

            elif status == ComplianceStatus.N_A.value:
                na_count += 1
                applicable_count -= 1
                total_possible_points -= req_weight

        # Raw Score
        if total_possible_points > 0:
            raw_score = (total_earned_points / total_possible_points) * 100.0
        else:
            raw_score = 100.0 if total_reqs > 0 else 0.0

        raw_score = max(0.0, min(100.0, raw_score))
        final_score = raw_score
        is_capped = False
        cap_reason = None

        # Apply Capping Invariants
        if is_debarred:
            final_score = cls.DEBARMENT_SCORE
            is_capped = True
            cap_reason = "DEBARMENT_OVERRIDE: Bidder is listed on government debarment/blacklist registry."

        elif has_mandatory_fail:
            if final_score > cls.MANDATORY_FAIL_CAP:
                final_score = cls.MANDATORY_FAIL_CAP
                is_capped = True
                cap_reason = f"MANDATORY_FAILURE_CAP: Score capped at {cls.MANDATORY_FAIL_CAP:.0f} due to failure of mandatory compliance requirement(s)."

        elif has_mandatory_missing:
            if final_score > cls.MANDATORY_MISSING_CAP:
                final_score = cls.MANDATORY_MISSING_CAP
                is_capped = True
                cap_reason = f"MANDATORY_MISSING_CAP: Score capped at {cls.MANDATORY_MISSING_CAP:.0f} due to missing mandatory documentation."

        # Check for Critical Contradictions (exclude dismissed findings)
        has_critical_contra = any(
            f.status == "CONTRADICTION" and f.severity in ("HIGH", "CRITICAL")
            for f in findings
            if getattr(f, "status", "") not in ("DISMISSED", "DISMISSED_BY_OFFICER")
        )
        if has_critical_contra and not is_debarred and not has_mandatory_fail:
            if final_score > cls.CRITICAL_CONTRADICTION_CAP:
                final_score = cls.CRITICAL_CONTRADICTION_CAP
                is_capped = True
                cap_reason = f"CRITICAL_CONTRADICTION_CAP: Score capped at {cls.CRITICAL_CONTRADICTION_CAP:.0f} due to high-severity cross-document inconsistency."

        return ComplianceScoreBreakdown(
            total_requirements=total_reqs,
            total_applicable=applicable_count,
            passed=pass_count,
            failed=fail_count,
            missing=missing_count,
            under_review=review_count,
            not_verified=not_verified_count,
            not_applicable=na_count,
            raw_score=raw_score,
            final_score=final_score,
            is_capped=is_capped,
            cap_reason=cap_reason,
            deductions=deductions,
        )
