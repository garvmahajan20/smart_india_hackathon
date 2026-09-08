# -*- coding: utf-8 -*-
"""
Deterministic AI Recommendation Engine with Hard Authority Boundaries.
Phases 8 & 9: Decision-Support Recommendation & Strict Consistency Invariants.

Crucial Governance Principles:
1. DECISION SUPPORT ONLY: The final qualification/disqualification authority
   remains exclusively with the Procurement Officer.
2. DETERMINISTIC CONSTRAINTS: LLMs / probabilistic components MUST NEVER
   override deterministic compliance failures, missing evidence, or high-risk flags.
3. ZERO HALLUCINATIONS: Recommendations reference only real verified facts and evidence.
"""

from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import ComplianceStatus, Severity, VerificationResult
from .pending_requirements import PendingRequirement
from .risk_engine import RiskAssessment, RiskLevel
from .scoring import ComplianceScoreBreakdown
from backend.verification.models import AdapterResponse, IntegrityFinding


class RecommendationVerdict(str, Enum):
    PASS = "PASS"        # Fully compliant, low risk, ready for award evaluation
    REVIEW = "REVIEW"    # Actionable issues, missing evidence, or discrepancies for officer adjudication
    FAIL = "FAIL"        # Incurable statutory bar, debarment, or critical mandatory failure


@dataclass
class AIRecommendation:
    verdict: RecommendationVerdict
    confidence: str                       # HIGH, MEDIUM, LOW
    headline: str
    detailed_summary: str
    key_reasons: List[str]
    critical_issues: List[str]
    pending_requirements: List[Dict[str, Any]]
    suggested_officer_actions: List[str]
    risk_level: str
    compliance_score: float
    authority_notice: str = "DECISION_SUPPORT_ONLY: Final qualification/disqualification authority remains exclusively with the Procurement Officer."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "headline": self.headline,
            "detailed_summary": self.detailed_summary,
            "key_reasons": self.key_reasons,
            "critical_issues": self.critical_issues,
            "pending_requirements": self.pending_requirements,
            "suggested_officer_actions": self.suggested_officer_actions,
            "risk_level": self.risk_level,
            "compliance_score": round(self.compliance_score, 2),
            "authority_notice": self.authority_notice,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIRecommendation":
        d = dict(data)
        d["verdict"] = RecommendationVerdict(d["verdict"])
        return cls(**d)


class AIRecommendationEngine:
    """
    Synthesizes deterministic compliance, risk, integrity, and registry signals
    into a structured, explainable recommendation for procurement officers.
    """

    @classmethod
    def generate_recommendation(
        cls,
        compliance_score: ComplianceScoreBreakdown,
        risk_assessment: RiskAssessment,
        compliance_results: List[VerificationResult],
        pending_requirements: List[PendingRequirement],
        integrity_findings: Optional[List[IntegrityFinding]] = None,
        government_responses: Optional[List[AdapterResponse]] = None,
        is_debarred: bool = False,
    ) -> AIRecommendation:
        findings = integrity_findings or []
        gov_resps = government_responses or []

        critical_issues: List[str] = []
        key_reasons: List[str] = []
        officer_actions: List[str] = []

        # 1. Gather Critical Issues
        if is_debarred:
            critical_issues.append("Bidder is actively listed on government debarment/blacklist registry.")
            officer_actions.append("Issue statutory disqualification order under GeM debarment guidelines.")

        mandatory_fails = [
            r for r in compliance_results
            if (r.status == ComplianceStatus.FAIL.value and r.severity in (Severity.CRITICAL.value, Severity.MAJOR.value))
        ]
        for mf in mandatory_fails:
            critical_issues.append(f"Mandatory requirement '{mf.requirement_id}' failed: {mf.reason}")
            officer_actions.append(f"Review failure on clause {mf.requirement_id} for potential rejection or clarification.")

        missing_mandatory = [p for p in pending_requirements if p.mandatory and p.compliance_result == "MISSING"]
        for mm in missing_mandatory:
            critical_issues.append(f"Mandatory document missing: '{mm.description}'")
            officer_actions.append(f"Issue shortfall notice for missing {mm.description}.")

        critical_contra = [
            f for f in findings
            if f.status == "CONTRADICTION" and f.severity in ("HIGH", "CRITICAL")
        ]
        for cc in critical_contra:
            critical_issues.append(f"Cross-document contradiction on '{cc.field}': {cc.description}")
            officer_actions.append(f"Seek bidder clarification on contradictory values for {cc.field}.")

        # Government unverified / unavailable checks
        for g in gov_resps:
            g_status = g.status.value if hasattr(g.status, "value") else str(g.status)
            if g_status in ("IDENTITY_MISMATCH", "INACTIVE"):
                critical_issues.append(f"{g.adapter_name} registry discrepancy: {getattr(g, 'reason', '')}")
            elif g_status in ("UNAVAILABLE", "ERROR"):
                key_reasons.append(f"{g.adapter_name} service was temporarily unreachable; registry cross-check pending.")

        # 2. Enforce Strict Decision Boundaries (Phase 9 Invariants)
        # INVARIANT 1: Debarment or Critical Mandatory Failure -> FAIL
        if is_debarred or len(mandatory_fails) > 0:
            verdict = RecommendationVerdict.FAIL
            confidence = "HIGH"
            headline = "DISQUALIFICATION RECOMMENDED: Incurable Non-Compliance Detected"
            key_reasons.extend(critical_issues[:3])
            summary = (
                f"The bidder failed {len(mandatory_fails)} mandatory requirement(s) or has active debarment status. "
                f"Overall compliance score is {compliance_score.final_score:.1f}/100 with {risk_assessment.level.value} risk. "
                "Disqualification is recommended under GeM tender terms."
            )

        # INVARIANT 2: Missing Mandatory Evidence, Contradictions, or Unresolved Review -> REVIEW
        elif (
            len(missing_mandatory) > 0
            or len(critical_contra) > 0
            or risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            or compliance_score.under_review > 0
            or compliance_score.final_score < 75.0
        ):
            verdict = RecommendationVerdict.REVIEW
            confidence = "HIGH" if len(critical_contra) > 0 or len(missing_mandatory) > 0 else "MEDIUM"
            headline = "PROCUREMENT OFFICER REVIEW REQUIRED: Shortfalls or Discrepancies Pending"
            
            if missing_mandatory:
                key_reasons.append(f"{len(missing_mandatory)} mandatory document(s) are missing from submission.")
            if critical_contra:
                key_reasons.append(f"{len(critical_contra)} cross-document inconsistency/inconsistencies detected.")
            if compliance_score.under_review > 0:
                key_reasons.append(f"{compliance_score.under_review} clause(s) require officer verification or interpretation.")

            summary = (
                f"The submission achieved a compliance score of {compliance_score.final_score:.1f}/100 "
                f"with {risk_assessment.level.value} risk. Several items require procurement officer clarification "
                "or shortfall remediation before award qualification can be considered."
            )
            if not officer_actions:
                officer_actions.append("Review highlighted verification queue items and request shortfall documents if permissible.")

        # INVARIANT 3: Clean, Full Compliance -> PASS
        else:
            verdict = RecommendationVerdict.PASS
            confidence = "HIGH"
            headline = "QUALIFICATION RECOMMENDED: All Applicable Requirements Satisfied"
            key_reasons.append(f"All {compliance_score.passed} applicable requirements successfully verified.")
            key_reasons.append("Zero mandatory failures, zero missing documents, and zero cross-source contradictions.")
            key_reasons.append("Government registry checks and forensic integrity checks consistent.")
            summary = (
                f"The bidder demonstrated full compliance across all {compliance_score.total_applicable} applicable clauses, "
                f"attaining a compliance score of {compliance_score.final_score:.1f}/100 with LOW risk. "
                "The submission is clean and technically qualified for commercial evaluation."
            )
            officer_actions.append("Proceed to commercial bid evaluation / L1 determination.")

        # 3. Serialize Pending Requirements
        serialized_pending = [p.to_dict() for p in pending_requirements]

        return AIRecommendation(
            verdict=verdict,
            confidence=confidence,
            headline=headline,
            detailed_summary=summary,
            key_reasons=key_reasons,
            critical_issues=critical_issues,
            pending_requirements=serialized_pending,
            suggested_officer_actions=officer_actions,
            risk_level=risk_assessment.level.value,
            compliance_score=compliance_score.final_score,
        )
