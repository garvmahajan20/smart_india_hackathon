# -*- coding: utf-8 -*-
"""
Tests for Procurement Officer Adjudication & Human Override Engine.
Verifies:
1. Authority & Accountability: Fail-closed validation for justifications and officer IDs.
2. Deterministic Re-evaluation: Hard score cap lifting (missing mandatory, contradiction),
   risk recalculation, and recommendation updates.
3. Provenance DAG Integration: Acyclic DAG maintenance with OFFICER_ADJUDICATION nodes.
4. Audit Trail & Deterministic Replay: Immutable cryptographic hashing and replay verifiability.
5. REST API Endpoints: End-to-end HTTP testing of adjudication, audit trail, and replay.
"""

import unittest
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from backend.api.app import app, _orchestrator
from backend.core.adjudication import (
    AdjudicationDecision,
    AdjudicationTargetType,
    OfficerAdjudicationRecord,
    OfficerAdjudicationRequest,
    ProcurementOfficerAdjudicationEngine,
)
from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.provenance_dag import (
    EdgeType,
    NodeType,
    ProvenanceDAGBuilder,
)
from backend.core.scoring import ComplianceScoringEngine
from backend.orchestration.aggregator import VerificationAggregator
from backend.orchestration.models import (
    AggregatedVerification,
    HumanReviewItem,
    VerificationDossier,
)
from backend.verification.models import IntegrityFinding


class TestOfficerAdjudicationEngine(unittest.TestCase):
    """Unit and adversarial tests for the Procurement Officer Adjudication Engine."""

    def setUp(self):
        self.req_mandatory = TenderRequirement(
            requirement_id="REQ-MANDATORY-01",
            tender_id="TENDER-TEST-001",
            category="TECHNICAL_SPECIFICATION",
            description="Mandatory OEM Authorization Certificate is required",
            operator="EXISTS",
            expected_value=True,
            field="oem_authorization",
            mandatory=True,
        )
        self.req_optional = TenderRequirement(
            requirement_id="REQ-OPTIONAL-02",
            tender_id="TENDER-TEST-001",
            category="EXPERIENCE",
            description="Minimum 3 years past experience",
            operator=">=",
            expected_value=3,
            field="past_experience_years",
            mandatory=False,
        )

        self.fact_exp = BidderFact(
            fact_id="FACT-EXP-01",
            bid_id="BID-TEST-001",
            field="past_experience_years",
            value=5,
            source_document="bid_experience.pdf",
            page=1,
            extraction_confidence=0.98,
        )

        # Baseline: REQ-MANDATORY-01 fails/missing -> creates hard cap at 55
        self.res_mandatory_fail = VerificationResult(
            verification_id="VERIF-TEST-01",
            requirement_id="REQ-MANDATORY-01",
            bid_id="BID-TEST-001",
            status=ComplianceStatus.MISSING.value,
            severity=Severity.CRITICAL.value,
            expected=True,
            actual=None,
            operator_used="EXISTS",
            reason="Required mandatory document 'oem_authorization' was not provided in bid submission.",
            requires_human_review=True,
        )
        self.res_exp_pass = VerificationResult(
            verification_id="VERIF-TEST-02",
            requirement_id="REQ-OPTIONAL-02",
            bid_id="BID-TEST-001",
            status=ComplianceStatus.PASS.value,
            severity=Severity.INFO.value,
            expected=">= 3",
            actual=5,
            operator_used=">=",
            reason="Experience requirement satisfied (5 >= 3 years).",
            requires_human_review=False,
            fact_id="FACT-EXP-01",
        )

        self.review_item = HumanReviewItem(
            review_id="REV-MANDATORY-01",
            bid_id="BID-TEST-001",
            tender_id="TENDER-TEST-001",
            category="MISSING_MANDATORY_DOCUMENT",
            severity="CRITICAL",
            reason="Mandatory OEM Authorization Certificate missing from bid submission.",
            related_verification_id="REQ-MANDATORY-01",
            status="PENDING",
        )

        self.aggregator = VerificationAggregator()
        self.aggregated = self.aggregator.aggregate(
            tender_id="TENDER-TEST-001",
            bid_id="BID-TEST-001",
            compliance_results=[self.res_mandatory_fail, self.res_exp_pass],
            integrity_findings=[],
            government_responses=[],
            requirements=[self.req_mandatory, self.req_optional],
            facts=[self.fact_exp],
        )
        # Ensure review item is populated
        self.aggregated.human_review_items = [self.review_item.to_dict()]

        # Generate corresponding dossier
        dag = ProvenanceDAGBuilder.build(
            requirements=[self.req_mandatory, self.req_optional],
            facts=[self.fact_exp],
            results=[self.res_mandatory_fail, self.res_exp_pass],
            integrity_findings=[],
            human_review_items=self.aggregated.human_review_items,
            bid_id="BID-TEST-001",
            tender_id="TENDER-TEST-001",
        )

        self.dossier = VerificationDossier(
            tender={"tender_id": "TENDER-TEST-001", "requirements": [self.req_mandatory.to_dict(), self.req_optional.to_dict()]},
            bidder={"bid_id": "BID-TEST-001", "facts": [self.fact_exp.to_dict()]},
            compliance_summary={"overall_status": self.aggregated.overall_status},
            integrity_summary={"integrity_status": self.aggregated.integrity_status},
            verification_results=self.aggregated.verification_results,
            government_checks=[],
            evidence=[],
            anomalies=[],
            human_review_items=self.aggregated.human_review_items,
            audit_metadata={"verification_id": self.aggregated.verification_id, "deterministic_run_id": self.aggregated.deterministic_run_id},
            provenance_graph=dag.to_dict(),
            compliance_score=self.aggregated.compliance_score_breakdown,
            risk_assessment=self.aggregated.risk_assessment,
            recommendation=self.aggregated.recommendation,
            pending_requirements=self.aggregated.pending_requirements,
            adjudications=[],
        )

    def test_baseline_has_missing_mandatory_hard_cap(self):
        """Precondition: missing mandatory document enforces score <= 55 and risk HIGH/CRITICAL."""
        self.assertLessEqual(self.aggregated.compliance_score, 55.0)
        self.assertIn(self.aggregated.risk_level, ("HIGH", "CRITICAL"))
        self.assertEqual(self.aggregated.overall_status, "REVIEW")

    def test_adjudication_waive_lifts_mandatory_score_cap_and_resolves_review(self):
        """Test officer waives missing requirement, lifting score cap to 100 and dropping risk."""
        request = OfficerAdjudicationRequest(
            target_id="REV-MANDATORY-01",
            decision=AdjudicationDecision.WAIVE.value,
            officer_id="OFFICER-789",
            officer_name="Shri R. K. Verma",
            officer_role="Executive Director / Procurement Authority",
            justification="Statutory exemption granted as bidder is OEM itself, documented in certificate doc-99.",
            reference_document="oem_incorporation_cert.pdf",
        )

        updated_agg, updated_dos, record = ProcurementOfficerAdjudicationEngine.apply_adjudication(
            aggregated=self.aggregated,
            dossier=self.dossier,
            request=request,
        )

        # 1. Audit record verified
        self.assertEqual(record.decision, "WAIVE")
        self.assertEqual(record.officer_id, "OFFICER-789")
        self.assertTrue(len(record.audit_hash) == 64)

        # 2. Review item status resolved
        self.assertEqual(updated_agg.human_review_items[0]["status"], "RESOLVED")

        # 3. Verification result status updated to OVERRIDDEN_PASS
        res_0 = updated_agg.verification_results[0]
        self.assertEqual(res_0["status"], "OVERRIDDEN_PASS")
        self.assertIn("officer_override", res_0)

        # 4. Deterministic score recalculated: 55 hard cap lifted, score goes to 100.0
        self.assertEqual(updated_agg.compliance_score, 100.0)
        self.assertEqual(updated_agg.risk_level, "LOW")
        self.assertEqual(updated_agg.overall_status, "PASS")
        self.assertFalse(updated_agg.review_required)

        # 5. Provenance DAG verified: contains OFFICER_ADJUDICATION node and acyclic
        dag_dict = updated_dos.provenance_graph
        node_types = {n["node_type"] for n in dag_dict["nodes"]}
        self.assertIn("OFFICER_ADJUDICATION", node_types)
        adj_nodes = [n for n in dag_dict["nodes"] if n["node_type"] == "OFFICER_ADJUDICATION"]
        self.assertEqual(len(adj_nodes), 1)
        self.assertEqual(adj_nodes[0]["properties"]["officer_id"], "OFFICER-789")

    def test_adjudication_dismiss_contradiction_lifts_contradiction_cap(self):
        """Test officer dismisses cross-document discrepancy, lifting 65 cap."""
        contradiction = IntegrityFinding(
            finding_id="INT-CONTRA-01",
            bid_id="BID-TEST-001",
            finding_type="CROSS_DOCUMENT_VALUE_CONFLICT",
            field="annual_turnover",
            severity="HIGH",
            status="CONTRADICTION",
            description="Turnover discrepancy between balance sheet (15 Cr) and bid form (14.8 Cr).",
            value_a=15.0,
            value_b=14.8,
            evidence_a={"document": "audited_balance_sheet.pdf", "page": 1},
            evidence_b={"document": "bid_form.pdf", "page": 2},
            requires_human_review=True,
        )
        self.aggregated.contradictions = [contradiction.to_dict()]
        self.aggregated.integrity_status = "CONTRADICTIONS_DETECTED"

        # Baseline score calculation with contradiction enforces 65 cap
        score_res = ComplianceScoringEngine.calculate_score(
            requirements=[self.req_optional],
            compliance_results=[self.res_exp_pass],
            integrity_findings=[contradiction],
            facts=[self.fact_exp],
        )
        self.assertLessEqual(score_res.final_score, 65.0)

        request = OfficerAdjudicationRequest(
            target_id="INT-CONTRA-01",
            decision=AdjudicationDecision.DISMISS.value,
            officer_id="OFFICER-456",
            officer_name="Dr. S. Nair",
            justification="Discrepancy is rounding difference between net and gross audited turnover; both exceed threshold.",
        )

        updated_agg, updated_dos, record = ProcurementOfficerAdjudicationEngine.apply_adjudication(
            aggregated=self.aggregated,
            dossier=self.dossier,
            request=request,
        )

        self.assertEqual(record.decision, "DISMISS")
        self.assertEqual(updated_agg.contradictions[0]["status"], "DISMISSED")

    def test_adjudication_confirm_fail_locks_status(self):
        """Test officer confirms non-compliance or fraudulent claim, locking status to FAIL."""
        request = OfficerAdjudicationRequest(
            target_id="REQ-OPTIONAL-02",
            decision=AdjudicationDecision.CONFIRM_FAIL.value,
            officer_id="OFFICER-101",
            officer_name="Inspector General",
            justification="Work orders submitted for experience were forged; verified with issuing department.",
        )

        updated_agg, updated_dos, record = ProcurementOfficerAdjudicationEngine.apply_adjudication(
            aggregated=self.aggregated,
            dossier=self.dossier,
            request=request,
        )

        self.assertEqual(record.decision, "CONFIRM_FAIL")
        res_exp = [r for r in updated_agg.verification_results if r["requirement_id"] == "REQ-OPTIONAL-02"][0]
        self.assertEqual(res_exp["status"], "OVERRIDDEN_FAIL")
        self.assertEqual(updated_agg.overall_status, "FAIL")

    def test_adversarial_fail_closed_validation(self):
        """Adversarial tests: empty officer, short justification, invalid decision, non-existent target."""
        # 1. Justification too short (< 10 chars)
        req_short = OfficerAdjudicationRequest(
            target_id="REV-MANDATORY-01",
            decision="ACCEPT",
            officer_id="OFF-1",
            officer_name="Officer",
            justification="ok",
        )
        with self.assertRaises(ValueError) as ctx:
            req_short.validate()
        self.assertIn("at least 10 characters", str(ctx.exception))

        # 2. Missing Officer ID
        req_no_id = OfficerAdjudicationRequest(
            target_id="REV-MANDATORY-01",
            decision="ACCEPT",
            officer_id="",
            officer_name="Officer",
            justification="Valid justification string that is long enough",
        )
        with self.assertRaises(ValueError) as ctx:
            req_no_id.validate()
        self.assertIn("Officer ID is mandatory", str(ctx.exception))

        # 3. Missing Officer Name
        req_no_name = OfficerAdjudicationRequest(
            target_id="REV-MANDATORY-01",
            decision="ACCEPT",
            officer_id="OFF-1",
            officer_name="   ",
            justification="Valid justification string that is long enough",
        )
        with self.assertRaises(ValueError) as ctx:
            req_no_name.validate()
        self.assertIn("Officer Name is mandatory", str(ctx.exception))

        # 4. Invalid Decision Enum
        req_bad_dec = OfficerAdjudicationRequest(
            target_id="REV-MANDATORY-01",
            decision="SUPER_PASS",
            officer_id="OFF-1",
            officer_name="Officer",
            justification="Valid justification string that is long enough",
        )
        with self.assertRaises(ValueError) as ctx:
            req_bad_dec.validate()
        self.assertIn("Invalid decision", str(ctx.exception))

        # 5. Non-existent Target ID
        req_missing_target = OfficerAdjudicationRequest(
            target_id="NON-EXISTENT-ID",
            decision="ACCEPT",
            officer_id="OFF-1",
            officer_name="Officer",
            justification="Valid justification string that is long enough",
        )
        with self.assertRaises(KeyError) as ctx:
            ProcurementOfficerAdjudicationEngine.apply_adjudication(
                self.aggregated, self.dossier, req_missing_target
            )
        self.assertIn("not found", str(ctx.exception))


class TestAdjudicationApiEndpoints(unittest.TestCase):
    """End-to-End REST API integration tests for adjudication, audit trail, and replay."""

    def setUp(self):
        self.client = TestClient(app)

        # Seed orchestrator session store with mock verification
        req = TenderRequirement(
            requirement_id="REQ-GST-01",
            tender_id="TENDER-API-01",
            category="STATUTORY",
            description="Valid GSTIN required",
            operator="EXISTS",
            expected_value=True,
            field="gstin",
            canonical_field="GSTIN",
            mandatory=True,
        )
        from backend.core.rule_engine import DeterministicRuleEngine
        rule_engine = DeterministicRuleEngine()
        comp_results = rule_engine.verify_bid([req], [])

        agg = VerificationAggregator().aggregate(
            tender_id="TENDER-API-01",
            bid_id="BID-API-01",
            compliance_results=comp_results,
            integrity_findings=[],
            government_responses=[],
            requirements=[req],
            facts=[],
        )
        dag = ProvenanceDAGBuilder.build(
            requirements=[req],
            facts=[],
            results=comp_results,
            integrity_findings=[],
            human_review_items=agg.human_review_items,
            bid_id="BID-API-01",
            tender_id="TENDER-API-01",
        )
        dos = VerificationDossier(
            tender={"tender_id": "TENDER-API-01", "requirements": [req.to_dict()]},
            bidder={"bid_id": "BID-API-01", "facts": []},
            compliance_summary={"overall_status": agg.overall_status},
            integrity_summary={"integrity_status": agg.integrity_status},
            verification_results=agg.verification_results,
            government_checks=[],
            evidence=[],
            anomalies=[],
            human_review_items=agg.human_review_items,
            audit_metadata={"verification_id": agg.verification_id, "deterministic_run_id": agg.deterministic_run_id},
            provenance_graph=dag.to_dict(),
            compliance_score=agg.compliance_score_breakdown,
            risk_assessment=agg.risk_assessment,
            recommendation=agg.recommendation,
            pending_requirements=agg.pending_requirements,
            adjudications=[],
        )

        _orchestrator._verifications[agg.verification_id] = agg
        _orchestrator._dossiers[agg.verification_id] = dos
        self.verif_id = agg.verification_id
        self.review_id = agg.human_review_items[0]["review_id"]

    def test_api_adjudicate_success(self):
        """Test POST /api/v1/verification/{id}/adjudicate applies override successfully."""
        payload = {
            "target_id": self.review_id,
            "decision": "WAIVE",
            "officer_id": "OFF-GOV-001",
            "officer_name": "Chief Procurement Officer",
            "officer_role": "Competent Authority",
            "justification": "Bidder is registered in an exempt category under Central Excise/GST notification 12/2017.",
        }
        resp = self.client.post(f"/api/v1/verification/{self.verif_id}/adjudicate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["adjudication"]["decision"], "WAIVE")
        self.assertEqual(data["updated_overall_status"], "PASS")
        self.assertEqual(data["remaining_open_reviews"], 0)

    def test_api_adjudicate_validation_failure(self):
        """Test POST /api/v1/verification/{id}/adjudicate returns 422/400 for short justification."""
        payload = {
            "target_id": self.review_id,
            "decision": "ACCEPT",
            "officer_id": "OFF-001",
            "officer_name": "Officer",
            "justification": "too short",  # < 10 chars
        }
        resp = self.client.post(f"/api/v1/verification/{self.verif_id}/adjudicate", json=payload)
        self.assertIn(resp.status_code, (400, 422))

    def test_api_audit_trail_endpoint(self):
        """Test GET /api/v1/verification/{id}/audit-trail returns recorded adjudications."""
        # First adjudicate
        payload = {
            "target_id": self.review_id,
            "decision": "ACCEPT",
            "officer_id": "OFF-AUDIT-99",
            "officer_name": "Director General",
            "justification": "Clarification submitted by bidder satisfies committee requirements.",
        }
        self.client.post(f"/api/v1/verification/{self.verif_id}/adjudicate", json=payload)

        # Then query audit trail
        resp = self.client.get(f"/api/v1/verification/{self.verif_id}/audit-trail")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["verification_id"], self.verif_id)
        self.assertEqual(data["adjudications_count"], 1)
        self.assertEqual(data["adjudications"][0]["officer_id"], "OFF-AUDIT-99")

    def test_api_replay_endpoint(self):
        """Test POST /api/v1/verification/{id}/replay executes independent deterministic replay."""
        resp = self.client.post(f"/api/v1/verification/{self.verif_id}/replay")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_match"])
        self.assertEqual(data["status"], "COMPLETE_MATCH")
        self.assertEqual(data["mismatches"], [])


if __name__ == "__main__":
    unittest.main()
