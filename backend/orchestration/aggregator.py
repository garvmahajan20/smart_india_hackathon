# -*- coding: utf-8 -*-
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.core.models import TenderRequirement, VerificationResult
from backend.core.pending_requirements import PendingRequirementExtractor
from backend.core.recommendation_engine import AIRecommendationEngine
from backend.core.risk_engine import DeterministicRiskEngine
from backend.core.scoring import ComplianceScoringEngine
from backend.verification.models import AdapterResponse, IntegrityFinding, VerificationStatus
from .models import (
    AggregatedVerification,
    ComplianceStatus,
    HumanReviewItem,
    IntegrityStatus,
    OverallStatus,
    ReviewCategory,
    ReviewItemStatus,
)

class VerificationAggregator:
    """
    Deterministic Verification Aggregation Engine.
    Combines Step 4 compliance results, Step 5 integrity findings, and
    government registry verification into tender/bid-level verdicts.
    Strictly preserves the architectural separation between compliance and integrity.
    """

    def aggregate(
        self,
        tender_id: str,
        bid_id: str,
        compliance_results: List[VerificationResult],
        integrity_findings: List[IntegrityFinding],
        government_responses: List[AdapterResponse],
        grounding_warnings: Optional[List[str]] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None,
        requirements: Optional[List[TenderRequirement]] = None,
        facts: Optional[List[Any]] = None,
        tender_metadata: Optional[Dict[str, Any]] = None,
    ) -> AggregatedVerification:
        """
        Executes deterministic aggregation logic over all verification signals.
        """
        grounding_warnings = grounding_warnings or []
        extraction_metadata = extraction_metadata or {}

        # 1. Deterministic Run Identifier
        seed_str = f"{tender_id}:{bid_id}:{len(compliance_results)}:{len(integrity_findings)}:{len(government_responses)}"
        deterministic_run_id = f"RUN-{hashlib.sha256(seed_str.encode('utf-8')).hexdigest()[:12].upper()}"
        verification_id = f"VERIF-{tender_id}-{bid_id}"

        # 2. Compliance Evaluation
        critical_fails = 0
        major_fails = 0
        missing_count = 0
        review_count = 0
        pass_count = 0
        total_compliance = len(compliance_results)

        human_review_items: List[HumanReviewItem] = []
        review_idx = 0

        serialized_compliance = []
        evidence_count = 0

        for r in compliance_results:
            serialized_compliance.append(r.to_dict())
            if r.evidence:
                evidence_count += len(r.evidence)

            if r.status == "FAIL":
                if r.severity == "CRITICAL":
                    critical_fails += 1
                else:
                    major_fails += 1
            elif r.status == "MISSING":
                missing_count += 1
            elif r.status in ["REVIEW", "PARTIAL"]:
                review_count += 1
            elif r.status == "PASS":
                pass_count += 1

            # Route compliance items requiring review
            if r.requires_human_review or r.status in ["REVIEW", "PARTIAL", "MISSING"]:
                review_idx += 1
                cat = ReviewCategory.MISSING_EVIDENCE.value if r.status == "MISSING" else ReviewCategory.AMBIGUOUS_COMPLIANCE.value
                human_review_items.append(HumanReviewItem(
                    review_id=f"REV-{bid_id}-{review_idx:03d}",
                    bid_id=bid_id,
                    tender_id=tender_id,
                    category=cat,
                    severity=r.severity or "MAJOR",
                    reason=f"Requirement '{r.requirement_id}': {r.reason}",
                    evidence_references=[e.to_dict() if hasattr(e, 'to_dict') else e for e in r.evidence],
                    source_documents=list(set([e.document if hasattr(e, 'document') else e.get('document', '') for e in r.evidence if e])),
                    source_pages=list(set([e.page if hasattr(e, 'page') else e.get('page', 1) for e in r.evidence if e])),
                    related_verification_id=r.verification_id,
                ))

        # Determine Compliance Status
        if critical_fails > 0 or major_fails > 0:
            compliance_status = ComplianceStatus.FAIL.value
        elif missing_count > 0:
            compliance_status = ComplianceStatus.MISSING.value
        elif review_count > 0:
            compliance_status = ComplianceStatus.REVIEW.value
        elif pass_count == total_compliance and total_compliance > 0:
            compliance_status = ComplianceStatus.PASS.value
        else:
            compliance_status = ComplianceStatus.REVIEW.value if total_compliance == 0 else ComplianceStatus.PARTIAL.value

        # 3. Integrity / Contradiction Evaluation
        contradiction_count = 0
        integrity_review_count = 0
        serialized_contradictions = []

        for finding in integrity_findings:
            serialized_contradictions.append(finding.to_dict())
            if finding.status == "CONTRADICTION":
                contradiction_count += 1
            elif finding.status == "REVIEW":
                integrity_review_count += 1

            if finding.requires_human_review or finding.status in ["CONTRADICTION", "REVIEW"]:
                review_idx += 1
                human_review_items.append(HumanReviewItem(
                    review_id=f"REV-{bid_id}-{review_idx:03d}",
                    bid_id=bid_id,
                    tender_id=tender_id,
                    category=ReviewCategory.INTEGRITY_CONTRADICTION.value,
                    severity="CRITICAL" if finding.severity == "HIGH" else "MAJOR",
                    reason=f"Cross-document contradiction on '{finding.field}': {finding.description}",
                    evidence_references=[finding.evidence_a, finding.evidence_b],
                    source_documents=[finding.evidence_a.get("document", ""), finding.evidence_b.get("document", "")],
                    source_pages=[finding.evidence_a.get("page", 1), finding.evidence_b.get("page", 1)],
                    related_verification_id=finding.finding_id,
                ))

        if contradiction_count > 0:
            integrity_status = IntegrityStatus.CONTRADICTION.value
        elif integrity_review_count > 0:
            integrity_status = IntegrityStatus.REVIEW.value
        else:
            integrity_status = IntegrityStatus.CONSISTENT.value

        # 4. Government Registry Evaluation
        serialized_gov = []
        is_debarred = False
        debarment_reason = ""

        for gov_resp in government_responses:
            serialized_gov.append(gov_resp.to_dict())

            # Check for debarment
            resp_status = gov_resp.status.value if hasattr(gov_resp.status, "value") else str(gov_resp.status)
            resp_reason = getattr(gov_resp, "reason", getattr(gov_resp, "message", ""))
            resp_data = getattr(gov_resp, "matched_entity", getattr(gov_resp, "data", {})) or {}

            if gov_resp.adapter_name == "DebarmentAdapter":
                if resp_status == "DEBARRED" or resp_data.get("status") == "DEBARRED":
                    is_debarred = True
                    debarment_reason = resp_reason
                    review_idx += 1
                    human_review_items.append(HumanReviewItem(
                        review_id=f"REV-{bid_id}-{review_idx:03d}",
                        bid_id=bid_id,
                        tender_id=tender_id,
                        category=ReviewCategory.DEBARMENT_ALERT.value,
                        severity="CRITICAL",
                        reason=f"Debarment Registry Alert: {resp_reason}",
                        evidence_references=[resp_data],
                        source_documents=["GOVERNMENT_DEBARMENT_REGISTRY"],
                        source_pages=[1],
                        related_verification_id=gov_resp.adapter_name,
                    ))

            # Check for government identity/status mismatch
            elif resp_status in ["IDENTITY_MISMATCH", "INACTIVE", "SUSPENDED", "REVIEW"]:
                review_idx += 1
                human_review_items.append(HumanReviewItem(
                    review_id=f"REV-{bid_id}-{review_idx:03d}",
                    bid_id=bid_id,
                    tender_id=tender_id,
                    category=ReviewCategory.GOVERNMENT_MISMATCH.value,
                    severity="MAJOR",
                    reason=f"{gov_resp.adapter_name} mismatch: {resp_reason}",
                    evidence_references=[resp_data],
                    source_documents=[gov_resp.adapter_name],
                    source_pages=[1],
                    related_verification_id=gov_resp.adapter_name,
                ))

        # 5. Grounding Warnings Evaluation
        for warn in grounding_warnings:
            review_idx += 1
            human_review_items.append(HumanReviewItem(
                review_id=f"REV-{bid_id}-{review_idx:03d}",
                bid_id=bid_id,
                tender_id=tender_id,
                category=ReviewCategory.GROUNDING_FAILURE.value,
                severity="MAJOR",
                reason=f"Evidence Grounding Alert: {warn}",
                evidence_references=[],
                source_documents=[],
                source_pages=[],
            ))

        # 6. Overall Status Determination (Phase 4 Rules)
        # Rule 1 & 2: Any CRITICAL or MAJOR compliance failure -> FAIL
        # Debarred -> FAIL
        if is_debarred:
            overall_status = OverallStatus.FAIL.value
        elif compliance_status == ComplianceStatus.FAIL.value:
            overall_status = OverallStatus.FAIL.value
        elif compliance_status in [ComplianceStatus.MISSING.value, ComplianceStatus.REVIEW.value]:
            overall_status = OverallStatus.REVIEW.value
        elif compliance_status == ComplianceStatus.PASS.value:
            # Rule 6: Integrity contradiction alone MUST NOT change compliance PASS into FAIL!
            # Instead, it flags overall_status as REVIEW for procurement officer adjudication.
            if integrity_status in [IntegrityStatus.CONTRADICTION.value, IntegrityStatus.REVIEW.value] or len(human_review_items) > 0:
                overall_status = OverallStatus.REVIEW.value
            else:
                overall_status = OverallStatus.PASS.value
        else:
            overall_status = OverallStatus.REVIEW.value

        review_required = (overall_status == OverallStatus.REVIEW.value) or (len(human_review_items) > 0)
        anomaly_count = contradiction_count + integrity_review_count + (1 if is_debarred else 0)

        # 7. Synthesize Effective Requirements if not explicitly provided
        effective_reqs = requirements or [
            TenderRequirement(
                requirement_id=r.requirement_id,
                tender_id=tender_id,
                category="COMPLIANCE",
                description=f"Clause {r.requirement_id}",
                operator=r.operator_used or "==",
                mandatory=(r.severity in ("CRITICAL", "MAJOR")),
            )
            for r in compliance_results
        ]

        # 8. Deterministic Scoring Engine (Phase 6)
        score_breakdown = ComplianceScoringEngine.calculate_score(
            requirements=effective_reqs,
            compliance_results=compliance_results,
            integrity_findings=integrity_findings,
            is_debarred=is_debarred,
            facts=facts,
            tender_metadata=tender_metadata,
        )

        # 9. Deterministic Risk Engine (Phase 7)
        risk_assessment = DeterministicRiskEngine.assess_risk(
            compliance_results=compliance_results,
            integrity_findings=integrity_findings,
            government_responses=government_responses,
            grounding_warnings=grounding_warnings,
            is_debarred=is_debarred,
            debarment_reason=debarment_reason if is_debarred else None,
        )

        # 10. Structured Pending Requirements Extraction (Phase 4)
        pending_items = PendingRequirementExtractor.extract_pending_requirements(
            requirements=effective_reqs,
            compliance_results=compliance_results,
            facts=facts or [],
            government_responses=government_responses,
            tender_metadata=tender_metadata,
        )

        # 11. AI Recommendation Engine (Phases 8 & 9)
        ai_recommendation = AIRecommendationEngine.generate_recommendation(
            compliance_score=score_breakdown,
            risk_assessment=risk_assessment,
            compliance_results=compliance_results,
            pending_requirements=pending_items,
            integrity_findings=integrity_findings,
            government_responses=government_responses,
            is_debarred=is_debarred,
        )

        return AggregatedVerification(
            verification_id=verification_id,
            tender_id=tender_id,
            bid_id=bid_id,
            overall_status=overall_status,
            compliance_status=compliance_status,
            integrity_status=integrity_status,
            verification_results=serialized_compliance,
            critical_failures=critical_fails,
            major_failures=major_fails,
            review_required=review_required,
            evidence_count=evidence_count,
            anomaly_count=anomaly_count,
            government_checks=serialized_gov,
            contradictions=serialized_contradictions,
            human_review_items=[item.to_dict() for item in human_review_items],
            deterministic_run_id=deterministic_run_id,
            processing_metadata={
                "debarred": is_debarred,
                "debarment_reason": debarment_reason if is_debarred else None,
                "total_compliance_checks": total_compliance,
                "passed_compliance_checks": pass_count,
                "contradiction_findings": len(integrity_findings),
                "government_checks_run": len(government_responses),
                "extraction_mode": extraction_metadata.get("mode", "MOCK"),
                "active_model": extraction_metadata.get("model", "gemini-3.8-flash"),
            },
            compliance_score=score_breakdown.final_score,
            compliance_score_breakdown=score_breakdown.to_dict(),
            risk_level=risk_assessment.level.value,
            risk_assessment=risk_assessment.to_dict(),
            recommendation=ai_recommendation.to_dict(),
            pending_requirements=[p.to_dict() for p in pending_items],
        )

