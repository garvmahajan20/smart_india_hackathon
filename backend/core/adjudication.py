# -*- coding: utf-8 -*-
"""
Deterministic Procurement Officer Adjudication & Override Engine.
Phase 10B.6: Human-in-the-Loop Governance & Tamper-Evident Override System.

Core Governance Axioms:
1. HUMAN AUTHORITY: The final qualification/disqualification authority
   remains exclusively with the Procurement Officer.
2. ACCOUNTABILITY: Every override requires an identified officer, authenticated role,
   explicit mandatory justification (>= 10 chars), and immutable audit record.
3. DETERMINISTIC RE-EVALUATION: Overrides deterministically update compliance scores,
   hard penalty caps, risk levels, and recommendations without probabilistic drift.
4. AUDIT TAMPER-EVIDENCE: All adjudications are cryptographically hashed and linked
   in the Provenance DAG.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field as dc_field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .models import BidderFact, ComplianceStatus, Severity, TenderRequirement, VerificationResult
from .pending_requirements import PendingRequirementExtractor
from .provenance_dag import ProvenanceDAGBuilder
from .recommendation_engine import AIRecommendationEngine
from .risk_engine import DeterministicRiskEngine
from .scoring import ComplianceScoringEngine
from backend.verification.models import AdapterResponse, IntegrityFinding


class AdjudicationDecision(str, Enum):
    ACCEPT = "ACCEPT"            # Officer accepts document/explanation; requirement passes
    WAIVE = "WAIVE"              # Officer waives clause under statutory/GTC discretionary authority
    CONFIRM_FAIL = "CONFIRM_FAIL"# Officer confirms non-compliance or fraud; clause/bid fails
    DISMISS = "DISMISS"          # Officer dismisses false-positive anomaly or discrepancy


class AdjudicationTargetType(str, Enum):
    REVIEW_ITEM = "REVIEW_ITEM"
    REQUIREMENT = "REQUIREMENT"
    INTEGRITY_FINDING = "INTEGRITY_FINDING"
    BID_VERDICT = "BID_VERDICT"


@dataclass
class OfficerAdjudicationRequest:
    target_id: str
    decision: str
    officer_id: str
    officer_name: str
    justification: str
    officer_role: str = "Competent Authority / Procurement Officer"
    reference_document: Optional[str] = None
    target_type: Optional[str] = None
    adjudication_id: Optional[str] = None
    timestamp: Optional[str] = None

    def validate(self) -> None:
        if not self.officer_id or not self.officer_id.strip():
            raise ValueError("Officer ID is mandatory for accountability.")
        if not self.officer_name or not self.officer_name.strip():
            raise ValueError("Officer Name is mandatory for accountability.")
        if not self.justification or len(self.justification.strip()) < 10:
            raise ValueError("Justification must be at least 10 characters detailing official basis for decision.")
        valid_decisions = {d.value for d in AdjudicationDecision}
        if self.decision.upper() not in valid_decisions:
            raise ValueError(f"Invalid decision '{self.decision}'. Allowed decisions: {sorted(valid_decisions)}")


@dataclass
class OfficerAdjudicationRecord:
    adjudication_id: str
    target_type: str
    target_id: str
    decision: str
    officer_id: str
    officer_name: str
    officer_role: str
    justification: str
    reference_document: Optional[str]
    previous_status: str
    new_status: str
    applied_at: str
    audit_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OfficerAdjudicationRecord":
        return cls(**data)


class ProcurementOfficerAdjudicationEngine:
    """
    Deterministic human-in-the-loop adjudication engine.
    Executes authoritative overrides, lifts/applies penalty caps,
    and recalculates system state with zero probabilistic components.
    """

    @classmethod
    def apply_adjudication(
        cls,
        aggregated: Any,
        dossier: Any,
        request: OfficerAdjudicationRequest,
    ) -> Tuple[Any, Any, OfficerAdjudicationRecord]:
        """
        Applies officer adjudication to aggregated verification and dossier,
        performing deterministic re-evaluation and audit trail recording.
        """
        # 1. Validate Request (Fail-closed)
        request.validate()

        decision = AdjudicationDecision(request.decision.upper())
        timestamp = request.timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        adj_id = request.adjudication_id or f"ADJ-{int(time.time() * 1000)}"

        target_id = request.target_id.strip()
        matched_target_type = None
        previous_status = "UNKNOWN"
        new_status = "UNKNOWN"

        # 2. Locate and Update Target in Verification Results / Review Items / Findings
        # Case A: Match by HumanReviewItem
        matched_review_item = None
        for item in aggregated.human_review_items:
            rev_id = item.get("review_id") if isinstance(item, dict) else item.review_id
            if rev_id == target_id:
                matched_review_item = item
                matched_target_type = AdjudicationTargetType.REVIEW_ITEM.value
                previous_status = item.get("status") if isinstance(item, dict) else item.status
                break

        # Case B: Match by VerificationResult requirement_id or verification_id
        matched_result_idx = None
        for idx, res_dict in enumerate(aggregated.verification_results):
            r_req_id = res_dict.get("requirement_id")
            r_verif_id = res_dict.get("verification_id")
            if target_id in (r_req_id, r_verif_id):
                matched_result_idx = idx
                if not matched_target_type:
                    matched_target_type = AdjudicationTargetType.REQUIREMENT.value
                    previous_status = res_dict.get("status", "UNKNOWN")
                break

        # Case C: Match by IntegrityFinding
        matched_finding_idx = None
        for idx, f_dict in enumerate(aggregated.contradictions):
            f_id = f_dict.get("finding_id")
            if f_id == target_id:
                matched_finding_idx = idx
                if not matched_target_type:
                    matched_target_type = AdjudicationTargetType.INTEGRITY_FINDING.value
                    previous_status = f_dict.get("status", "UNKNOWN")
                break

        if not matched_review_item and matched_result_idx is None and matched_finding_idx is None:
            raise KeyError(f"Target identifier '{target_id}' not found in verification.")

        # 3. Apply Decision Logic
        override_meta = {
            "adjudication_id": adj_id,
            "officer_id": request.officer_id,
            "officer_name": request.officer_name,
            "officer_role": request.officer_role,
            "decision": decision.value,
            "justification": request.justification,
            "reference_document": request.reference_document,
            "timestamp": timestamp,
            "previous_status": previous_status,
        }

        # If review item matched, update its status
        if matched_review_item:
            if decision in (AdjudicationDecision.ACCEPT, AdjudicationDecision.WAIVE, AdjudicationDecision.CONFIRM_FAIL):
                new_item_status = "RESOLVED"
            else:
                new_item_status = "DISMISSED"

            if isinstance(matched_review_item, dict):
                matched_review_item["status"] = new_item_status
                matched_review_item["adjudication"] = override_meta
            else:
                matched_review_item.status = new_item_status

            # Also check if review item points to a related verification result or finding
            related_id = matched_review_item.get("related_verification_id") if isinstance(matched_review_item, dict) else matched_review_item.related_verification_id
            if related_id:
                for idx, res_dict in enumerate(aggregated.verification_results):
                    if related_id in (res_dict.get("requirement_id"), res_dict.get("verification_id")):
                        matched_result_idx = idx
                        break
                for idx, f_dict in enumerate(aggregated.contradictions):
                    if related_id == f_dict.get("finding_id"):
                        matched_finding_idx = idx
                        break

        # If requirement result matched, update status and attach override
        if matched_result_idx is not None:
            res_dict = aggregated.verification_results[matched_result_idx]
            if decision in (AdjudicationDecision.ACCEPT, AdjudicationDecision.WAIVE):
                new_status = "OVERRIDDEN_PASS"
                res_dict["status"] = "OVERRIDDEN_PASS"
                res_dict["requires_human_review"] = False
                res_dict["officer_override"] = override_meta
            elif decision == AdjudicationDecision.CONFIRM_FAIL:
                new_status = "OVERRIDDEN_FAIL"
                res_dict["status"] = "OVERRIDDEN_FAIL"
                res_dict["requires_human_review"] = False
                res_dict["officer_override"] = override_meta
            else:
                new_status = res_dict.get("status", "UNKNOWN")

        # If finding matched, update status
        if matched_finding_idx is not None:
            f_dict = aggregated.contradictions[matched_finding_idx]
            if decision == AdjudicationDecision.DISMISS:
                new_status = "DISMISSED"
                f_dict["status"] = "DISMISSED"
                f_dict["dismissed_by_officer"] = True
                f_dict["officer_override"] = override_meta
            else:
                new_status = f_dict.get("status", "UNKNOWN")

        # 4. Deterministic Recalculation of Aggregated State
        # Convert dicts back to models for engines
        comp_results: List[VerificationResult] = [
            VerificationResult.from_dict(r) if isinstance(r, dict) else r
            for r in aggregated.verification_results
        ]
        int_findings: List[IntegrityFinding] = [
            IntegrityFinding.from_dict(f) if isinstance(f, dict) else f
            for f in aggregated.contradictions
        ]
        gov_resps: List[AdapterResponse] = [
            AdapterResponse.from_dict(g) if isinstance(g, dict) else g
            for g in aggregated.government_checks
        ]

        # Reconstruct requirements and facts from dossier if available
        reqs = [
            TenderRequirement.from_dict(r) if isinstance(r, dict) else r
            for r in (dossier.tender.get("requirements", []) if dossier and hasattr(dossier, "tender") else [])
        ]
        facts = [
            BidderFact.from_dict(f) if isinstance(f, dict) else f
            for f in (dossier.bidder.get("facts", []) if dossier and hasattr(dossier, "bidder") else [])
        ]

        # Active findings: exclude dismissed
        active_findings = [f for f in int_findings if f.status != "DISMISSED"]
        is_debarred = aggregated.processing_metadata.get("debarred", False)
        debar_reason = aggregated.processing_metadata.get("debarment_reason")

        # Re-score
        score_breakdown = ComplianceScoringEngine.calculate_score(
            requirements=reqs,
            compliance_results=comp_results,
            integrity_findings=active_findings,
            is_debarred=is_debarred,
            facts=facts,
        )

        # Re-evaluate Risk
        risk_assessment = DeterministicRiskEngine.assess_risk(
            compliance_results=comp_results,
            integrity_findings=active_findings,
            government_responses=gov_resps,
            grounding_warnings=[],
            is_debarred=is_debarred,
            debarment_reason=debar_reason,
        )

        # Re-evaluate Pending Requirements
        pending_items = PendingRequirementExtractor.extract_pending_requirements(
            requirements=reqs,
            compliance_results=comp_results,
            facts=facts,
            government_responses=gov_resps,
        )

        # Re-evaluate Recommendation
        recommendation = AIRecommendationEngine.generate_recommendation(
            compliance_score=score_breakdown,
            risk_assessment=risk_assessment,
            compliance_results=comp_results,
            pending_requirements=pending_items,
            integrity_findings=active_findings,
            government_responses=gov_resps,
            is_debarred=is_debarred,
        )

        # Recompute Critical & Major Fails
        critical_fails = 0
        major_fails = 0
        missing_count = 0
        review_count = 0
        pass_count = 0
        for r in comp_results:
            if r.status in ("FAIL", "OVERRIDDEN_FAIL"):
                if r.severity == Severity.CRITICAL.value:
                    critical_fails += 1
                else:
                    major_fails += 1
            elif r.status == "MISSING":
                missing_count += 1
            elif r.status in ("REVIEW", "PARTIAL"):
                review_count += 1
            elif r.status in ("PASS", "OVERRIDDEN_PASS"):
                pass_count += 1

        # Check Open Human Review Items
        open_review_items = [
            item for item in aggregated.human_review_items
            if (item.get("status") if isinstance(item, dict) else item.status) == "OPEN"
        ]

        # Determine Compliance Status
        if critical_fails > 0 or major_fails > 0:
            comp_status = ComplianceStatus.FAIL.value
        elif missing_count > 0:
            comp_status = ComplianceStatus.MISSING.value
        elif review_count > 0:
            comp_status = ComplianceStatus.REVIEW.value
        elif pass_count == len(comp_results) and len(comp_results) > 0:
            comp_status = ComplianceStatus.PASS.value
        else:
            comp_status = ComplianceStatus.PARTIAL.value

        # Determine Integrity Status
        if any(f.status == "CONTRADICTION" for f in active_findings):
            integ_status = "CONTRADICTION"
        else:
            integ_status = "CONSISTENT"

        # Determine Overall Status
        if is_debarred or critical_fails > 0 or major_fails > 0:
            overall_status = "FAIL"
        elif len(open_review_items) > 0 or missing_count > 0 or integ_status == "CONTRADICTION":
            overall_status = "REVIEW"
        else:
            overall_status = "PASS"

        # 5. Compute Audit Hash
        hash_seed = f"{adj_id}:{target_id}:{decision.value}:{request.officer_id}:{timestamp}:{request.justification}"
        audit_hash = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()

        record = OfficerAdjudicationRecord(
            adjudication_id=adj_id,
            target_type=matched_target_type or AdjudicationTargetType.REVIEW_ITEM.value,
            target_id=target_id,
            decision=decision.value,
            officer_id=request.officer_id,
            officer_name=request.officer_name,
            officer_role=request.officer_role,
            justification=request.justification,
            reference_document=request.reference_document,
            previous_status=previous_status,
            new_status=new_status,
            applied_at=timestamp,
            audit_hash=audit_hash,
        )

        # 6. Update Aggregated Verification
        aggregated.overall_status = overall_status
        aggregated.compliance_status = comp_status
        aggregated.integrity_status = integ_status
        aggregated.critical_failures = critical_fails
        aggregated.major_failures = major_fails
        aggregated.review_required = (len(open_review_items) > 0)
        aggregated.compliance_score = score_breakdown.final_score
        aggregated.compliance_score_breakdown = score_breakdown.to_dict()
        aggregated.risk_level = risk_assessment.level.value
        aggregated.risk_assessment = risk_assessment.to_dict()
        aggregated.recommendation = recommendation.to_dict()
        aggregated.pending_requirements = [p.to_dict() for p in pending_items]
        if not hasattr(aggregated, "adjudications"):
            aggregated.adjudications = []
        aggregated.adjudications.append(record.to_dict())

        # 7. Update Dossier
        dossier.compliance_summary["compliance_status"] = comp_status
        dossier.compliance_summary["overall_status"] = overall_status
        dossier.compliance_summary["critical_failures"] = critical_fails
        dossier.compliance_summary["major_failures"] = major_fails
        dossier.integrity_summary["integrity_status"] = integ_status
        dossier.verification_results = aggregated.verification_results
        dossier.anomalies = aggregated.contradictions
        dossier.human_review_items = aggregated.human_review_items
        dossier.compliance_score = score_breakdown.to_dict()
        dossier.risk_assessment = risk_assessment.to_dict()
        dossier.recommendation = recommendation.to_dict()
        dossier.pending_requirements = [p.to_dict() for p in pending_items]
        if not hasattr(dossier, "adjudications"):
            dossier.adjudications = []
        dossier.adjudications.append(record.to_dict())

        # Update Provenance DAG
        dag = ProvenanceDAGBuilder.build(
            requirements=reqs,
            facts=facts,
            results=comp_results,
            integrity_findings=active_findings,
            human_review_items=aggregated.human_review_items,
            bid_id=aggregated.bid_id,
            tender_id=aggregated.tender_id,
            adjudications=getattr(aggregated, "adjudications", []),
        )
        dag.validate()
        dossier.provenance_graph = dag.to_dict()

        return aggregated, dossier, record
