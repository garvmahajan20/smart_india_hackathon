# -*- coding: utf-8 -*-
"""
Deterministic Risk Assessment Engine.
Phase 7: Multi-Signal Objective Risk Evaluation.

Taxonomy: LOW, MEDIUM, HIGH, CRITICAL.

Risk is independently meaningful from the compliance score:
- Evaluates objective threat vectors including mandatory failures, missing evidence,
  cross-source contradictions, government mismatches, and forensic anomalies.
- Guarantees risk escalation: high score does not suppress critical risk signals.
"""

from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import ComplianceStatus, Severity, TenderRequirement, VerificationResult
from backend.verification.models import AdapterResponse, IntegrityFinding


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskFactor:
    code: str
    severity: str        # CRITICAL, HIGH, MEDIUM, LOW
    category: str        # DEBARMENT, MANDATORY_FAILURE, MISSING_EVIDENCE, CONTRADICTION, GOV_MISMATCH, UNCERTAINTY
    description: str
    trigger_source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "trigger_source": self.trigger_source,
        }


@dataclass
class RiskAssessment:
    level: RiskLevel
    risk_score: float             # 0.0 (clean) to 1.0 (maximum threat)
    risk_factors: List[RiskFactor] = dc_field(default_factory=list)
    mitigating_factors: List[str] = dc_field(default_factory=list)
    escalation_triggers: List[str] = dc_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "risk_score": round(self.risk_score, 3),
            "risk_factors": [rf.to_dict() for rf in self.risk_factors],
            "mitigating_factors": self.mitigating_factors,
            "escalation_triggers": self.escalation_triggers,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAssessment":
        factors = [RiskFactor(**f) for f in data.get("risk_factors", [])]
        d = dict(data)
        d["level"] = RiskLevel(d["level"])
        d["risk_factors"] = factors
        return cls(**d)


class DeterministicRiskEngine:
    """
    Pure deterministic risk calculator.
    Zero LLM calls, zero network operations.
    """

    @classmethod
    def assess_risk(
        cls,
        compliance_results: List[VerificationResult],
        integrity_findings: Optional[List[IntegrityFinding]] = None,
        government_responses: Optional[List[AdapterResponse]] = None,
        grounding_warnings: Optional[List[str]] = None,
        is_debarred: bool = False,
        debarment_reason: Optional[str] = None,
    ) -> RiskAssessment:
        findings = integrity_findings or []
        gov_resps = government_responses or []
        warnings = grounding_warnings or []

        risk_factors: List[RiskFactor] = []
        mitigating_factors: List[str] = []
        escalation_triggers: List[str] = []

        # 1. Debarment Evaluation
        if is_debarred:
            rf = RiskFactor(
                code="DEBARMENT_DETECTED",
                severity="CRITICAL",
                category="DEBARMENT",
                description=f"Bidder is listed on government debarment/blacklist registry: {debarment_reason or 'Active Debarment'}",
                trigger_source="GOVERNMENT_DEBARMENT_REGISTRY",
            )
            risk_factors.append(rf)
            escalation_triggers.append("Active Debarment on Government Registry")

        # 2. Compliance Results Evaluation
        mandatory_critical_fails = 0
        mandatory_fails = 0
        mandatory_missing = 0
        review_items = 0

        for r in compliance_results:
            st = r.status.upper() if isinstance(r.status, str) else r.status.value
            sev = r.severity.upper() if isinstance(r.severity, str) else r.severity.value

            if st == ComplianceStatus.FAIL.value:
                if sev == Severity.CRITICAL.value:
                    mandatory_critical_fails += 1
                    risk_factors.append(RiskFactor(
                        code="MANDATORY_CRITICAL_FAILURE",
                        severity="CRITICAL",
                        category="MANDATORY_FAILURE",
                        description=f"Critical mandatory failure on '{r.requirement_id}': {r.reason}",
                        trigger_source=r.verification_id,
                    ))
                    escalation_triggers.append(f"Critical Requirement Failed ({r.requirement_id})")
                else:
                    mandatory_fails += 1
                    risk_factors.append(RiskFactor(
                        code="MANDATORY_REQUIREMENT_FAILURE",
                        severity="HIGH",
                        category="MANDATORY_FAILURE",
                        description=f"Mandatory failure on '{r.requirement_id}': {r.reason}",
                        trigger_source=r.verification_id,
                    ))

            elif st == ComplianceStatus.MISSING.value:
                if sev in (Severity.CRITICAL.value, Severity.MAJOR.value):
                    mandatory_missing += 1
                    risk_factors.append(RiskFactor(
                        code="MANDATORY_EVIDENCE_MISSING",
                        severity="HIGH",
                        category="MISSING_EVIDENCE",
                        description=f"Mandatory documentation missing for '{r.requirement_id}': {r.reason}",
                        trigger_source=r.verification_id,
                    ))

            elif st in (ComplianceStatus.REVIEW.value, ComplianceStatus.PARTIAL.value) or r.requires_human_review:
                review_items += 1
                risk_factors.append(RiskFactor(
                    code="UNRESOLVED_COMPLIANCE_REVIEW",
                    severity="MEDIUM",
                    category="UNCERTAINTY",
                    description=f"Requirement '{r.requirement_id}' requires human review: {r.reason}",
                    trigger_source=r.verification_id,
                ))

        # 3. Contradiction & Integrity Evaluation
        critical_contradictions = 0
        for finding in findings:
            f_status = finding.status.upper() if isinstance(finding.status, str) else finding.status.value
            f_sev = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value

            if f_status == "CONTRADICTION":
                if f_sev in ("HIGH", "CRITICAL") or "NAME" in finding.finding_type or "GSTIN" in finding.finding_type or "PAN" in finding.finding_type:
                    critical_contradictions += 1
                    risk_factors.append(RiskFactor(
                        code="IDENTITY_OR_CRITICAL_CONTRADICTION",
                        severity="CRITICAL",
                        category="CONTRADICTION",
                        description=f"High-severity contradiction on '{finding.field}': {finding.description}",
                        trigger_source=finding.finding_id,
                    ))
                    escalation_triggers.append(f"Cross-document identity contradiction on {finding.field}")
                else:
                    risk_factors.append(RiskFactor(
                        code="CROSS_DOCUMENT_CONTRADICTION",
                        severity="HIGH",
                        category="CONTRADICTION",
                        description=f"Inconsistency on '{finding.field}': {finding.description}",
                        trigger_source=finding.finding_id,
                    ))

        # 4. Government Registry Evaluation
        for gov in gov_resps:
            g_status = gov.status.value if hasattr(gov.status, "value") else str(gov.status)
            g_reason = getattr(gov, "reason", "")

            if g_status in ("IDENTITY_MISMATCH", "SUSPENDED", "INACTIVE"):
                risk_factors.append(RiskFactor(
                    code="GOVERNMENT_REGISTRY_MISMATCH",
                    severity="HIGH",
                    category="GOV_MISMATCH",
                    description=f"{gov.adapter_name} returned {g_status}: {g_reason}",
                    trigger_source=gov.adapter_name,
                ))
                escalation_triggers.append(f"Government Registry Mismatch ({gov.adapter_name})")

            elif g_status in ("UNAVAILABLE", "ERROR") and any(term in gov.adapter_name.lower() for term in ("pan", "udyam", "debarment")):
                risk_factors.append(RiskFactor(
                    code="CRITICAL_GOVERNMENT_UNAVAILABLE",
                    severity="HIGH",
                    category="GOV_MISMATCH",
                    description=f"{gov.adapter_name} service unavailable during verification: {g_reason}",
                    trigger_source=gov.adapter_name,
                ))

        # 5. Grounding & Extraction Quality Warnings
        for w in warnings:
            risk_factors.append(RiskFactor(
                code="EVIDENCE_GROUNDING_WARNING",
                severity="MEDIUM",
                category="UNCERTAINTY",
                description=f"Grounding alert: {w}",
                trigger_source="EXTRACTION_PIPELINE",
            ))

        # 6. Mitigating Factors
        if not is_debarred:
            mitigating_factors.append("No adverse debarment records found on government registries.")
        if mandatory_critical_fails == 0 and mandatory_fails == 0:
            mitigating_factors.append("Zero mandatory clause failures detected in primary submission.")
        if critical_contradictions == 0 and len(findings) == 0:
            mitigating_factors.append("Cross-document consistency validated across all submitted sections.")

        # 7. Synthesize Deterministic Risk Level
        has_critical = any(rf.severity == "CRITICAL" for rf in risk_factors)
        has_high = any(rf.severity == "HIGH" for rf in risk_factors)
        has_medium = any(rf.severity == "MEDIUM" for rf in risk_factors)

        if has_critical:
            level = RiskLevel.CRITICAL
            score = 0.90 + min(0.10, len(risk_factors) * 0.02)
        elif has_high:
            level = RiskLevel.HIGH
            score = 0.65 + min(0.20, len(risk_factors) * 0.03)
        elif has_medium:
            level = RiskLevel.MEDIUM
            score = 0.35 + min(0.25, len(risk_factors) * 0.04)
        else:
            level = RiskLevel.LOW
            score = 0.05 + min(0.15, len(risk_factors) * 0.02)

        return RiskAssessment(
            level=level,
            risk_score=min(1.0, score),
            risk_factors=risk_factors,
            mitigating_factors=mitigating_factors,
            escalation_triggers=escalation_triggers,
        )
