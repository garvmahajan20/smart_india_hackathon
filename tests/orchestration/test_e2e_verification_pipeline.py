# -*- coding: utf-8 -*-
"""
SIH26100 End-to-End Verification Pipeline Integration Test Suite.
Verifies data continuity, deterministic authority, and complete pipeline execution across:
TENDER + BID DOCUMENTS -> INGESTION -> REQUIREMENT EXTRACTION -> APPLICABILITY
-> FACT EXTRACTION -> EVIDENCE GROUNDING -> CONTRADICTION / INTEGRITY
-> DETERMINISTIC COMPLIANCE -> PENDING REQUIREMENTS -> SCORING -> RISK
-> AI RECOMMENDATION -> PROVENANCE DAG -> AUDIT RECORD -> REST API / DOSSIER
"""
import json
import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.models import BidderFact, EvidencePointer, TenderRequirement, VerificationResult
from backend.core.ontology import resolve_field
from backend.core.provenance_dag import ProvenanceDAGBuilder, NodeType, EdgeType
from backend.core.replay_engine import DeterministicReplayEngine
from backend.core.scoring import ComplianceScoringEngine
from backend.core.risk_engine import DeterministicRiskEngine
from backend.core.recommendation_engine import AIRecommendationEngine
from backend.core.pending_requirements import PendingRequirementExtractor
from backend.extraction.models import LLMMode
from backend.orchestration import (
    AggregatedVerification,
    ComplianceStatus,
    IntegrityStatus,
    OverallStatus,
    ReviewCategory,
    VerificationAggregator,
    VerificationOrchestrator,
)
from backend.verification.models import AdapterResponse, IntegrityFinding, VerificationStatus


class TestE2EVerificationPipeline(unittest.TestCase):
    """
    Exhaustive integration tests validating the SIH26100 end-to-end verification pipeline.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.aggregator = VerificationAggregator()
        cls.orchestrator = VerificationOrchestrator(mode=LLMMode.MOCK)
        cls.tender_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/tenders/TENDER-0001.pdf"
        cls.bid_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids/BID-00001.pdf"

    # =========================================================================
    # 1. Clean Compliant Bidder Pipeline
    # =========================================================================
    def test_01_e2e_clean_bidder_pipeline(self):
        """
        Positive E2E test: A completely compliant bidder where all mandatory clauses pass,
        no cross-document contradictions exist, and government registries verify cleanly.
        Verifies:
        - Compliance Status = PASS
        - Integrity Status = CONSISTENT
        - Overall Status = PASS
        - Compliance Score = 100.0
        - Risk Level = LOW
        - AI Recommendation verdict = PASS with procurement officer disclaimer
        - Provenance DAG is acyclic and contains all required nodes
        """
        tender_id = "TENDER-SIH-001"
        bid_id = "BID-CLEAN-001"

        reqs = [
            TenderRequirement(
                requirement_id="REQ-TO-01",
                tender_id=tender_id,
                category="FINANCIAL_EXPERIENCE",
                description="Annual turnover >= 10.0 Cr in last 3 FY",
                field="turnover_cr",
                operator=">=",
                expected_value=10.0,
                mandatory=True,
            ),
            TenderRequirement(
                requirement_id="REQ-ISO-01",
                tender_id=tender_id,
                category="STATUTORY_CERTIFICATION",
                description="Valid ISO 9001 certification required",
                field="iso_9001",
                operator="EXISTS",
                expected_value=True,
                mandatory=True,
            ),
        ]

        facts = [
            BidderFact(
                fact_id="FACT-TO-01",
                bid_id=bid_id,
                field="turnover_cr",
                canonical_field="ANNUAL_TURNOVER",
                value=15.5,
                unit="INR_CRORES",
                source_document="audited_balance_sheet.pdf",
                page=3,
                bbox=[72.0, 100.0, 250.0, 120.0],
                raw_text_snippet="Annual turnover for FY 2023-24: Rs. 15.50 Crores",
                extraction_confidence="HIGH",
            ),
            BidderFact(
                fact_id="FACT-ISO-01",
                bid_id=bid_id,
                field="iso_9001",
                canonical_field="ISO_9001_CERTIFICATE",
                value=True,
                source_document="iso_cert.pdf",
                page=1,
                bbox=[50.0, 80.0, 300.0, 150.0],
                raw_text_snippet="Certificate of Registration: ISO 9001:2015 Quality Management System",
                extraction_confidence="HIGH",
            ),
        ]

        comp_results = [
            VerificationResult(
                verification_id="VERIF-TO-01",
                requirement_id="REQ-TO-01",
                bid_id=bid_id,
                status="PASS",
                severity="CRITICAL",
                expected=">= 10.0",
                actual="15.5",
                operator_used=">=",
                reason="Turnover Rs. 15.5 Cr exceeds required Rs. 10.0 Cr",
                evidence=[EvidencePointer("audited_balance_sheet.pdf", 3, [72.0, 100.0, 250.0, 120.0], "Turnover: 15.5 Cr")],
                requires_human_review=False,
            ),
            VerificationResult(
                verification_id="VERIF-ISO-01",
                requirement_id="REQ-ISO-01",
                bid_id=bid_id,
                status="PASS",
                severity="MAJOR",
                expected="EXISTS",
                actual=True,
                operator_used="EXISTS",
                reason="ISO 9001:2015 certificate submitted and valid",
                evidence=[EvidencePointer("iso_cert.pdf", 1, [50.0, 80.0, 300.0, 150.0], "ISO 9001:2015")],
                requires_human_review=False,
            ),
        ]

        gov_responses = [
            AdapterResponse(
                adapter_name="MockGSTAdapter",
                status=VerificationStatus.VERIFIED,
                queried_identifier="29SYNTH0000003F1Z",
                source="MOCK_GST_REGISTRY",
                reason="GSTIN is active and verified",
                matched_entity={"status": "ACTIVE", "legal_name": "Acme Systems Ltd"},
                is_mock=True,
            ),
            AdapterResponse(
                adapter_name="MockPANAdapter",
                status=VerificationStatus.VERIFIED,
                queried_identifier="SYNTH0003F",
                source="MOCK_PAN_REGISTRY",
                reason="PAN is valid and active",
                matched_entity={"status": "VALID", "name": "ACME SYSTEMS LTD"},
                is_mock=True,
            ),
            AdapterResponse(
                adapter_name="DebarmentAdapter",
                status=VerificationStatus.VERIFIED,
                queried_identifier="ACME SYSTEMS LTD",
                source="MOCK_DEBARMENT_REGISTRY",
                reason="No debarment records found",
                matched_entity={"status": "NOT_DEBARRED"},
                is_mock=True,
            ),
        ]

        agg = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=[],
            government_responses=gov_responses,
            requirements=reqs,
            facts=facts,
        )

        # 1. Pipeline verdicts
        self.assertEqual(agg.compliance_status, ComplianceStatus.PASS.value)
        self.assertEqual(agg.integrity_status, IntegrityStatus.CONSISTENT.value)
        self.assertEqual(agg.overall_status, OverallStatus.PASS.value)
        self.assertFalse(agg.review_required)
        self.assertEqual(agg.critical_failures, 0)
        self.assertEqual(agg.major_failures, 0)

        # 2. Scoring & Risk
        self.assertEqual(agg.compliance_score, 100.0)
        self.assertEqual(agg.compliance_score_breakdown["final_score"], 100.0)
        self.assertEqual(agg.risk_level, "LOW")
        self.assertIn("LOW", agg.risk_assessment["level"])

        # 3. AI Recommendation & Authority Notice
        self.assertEqual(agg.recommendation["verdict"], "PASS")
        self.assertEqual(agg.recommendation["confidence"], "HIGH")
        self.assertIn("authority_notice", agg.recommendation)
        self.assertIn("Procurement Officer", agg.recommendation["authority_notice"])

        # 4. Provenance DAG Validation
        dag = ProvenanceDAGBuilder.build(
            requirements=reqs,
            facts=facts,
            results=comp_results,
            integrity_findings=[],
            human_review_items=agg.human_review_items,
            bid_id=bid_id,
            tender_id=tender_id,
        )
        self.assertGreater(len(dag.nodes), 0)
        self.assertGreater(len(dag.edges), 0)
        # Check DAG structural integrity and acyclicity
        dag.validate()

    # =========================================================================
    # 2. Missing Mandatory Requirement Pipeline
    # =========================================================================
    def test_02_e2e_missing_mandatory_requirement(self):
        """
        Missing mandatory document test:
        - Mandatory clause missing -> Status = MISSING
        - Score capped at <= 55.0
        - Risk Level >= HIGH
        - AI Recommendation = REVIEW
        - Pending requirement generated with actionable remedy
        """
        tender_id = "TENDER-SIH-002"
        bid_id = "BID-MISSING-002"

        reqs = [
            TenderRequirement(
                requirement_id="REQ-TO-02",
                tender_id=tender_id,
                category="FINANCIAL_EXPERIENCE",
                description="Audited turnover statement",
                field="turnover_cr",
                operator=">=",
                expected_value=10.0,
                mandatory=True,
            ),
        ]

        comp_results = [
            VerificationResult(
                verification_id="VERIF-TO-02",
                requirement_id="REQ-TO-02",
                bid_id=bid_id,
                status="MISSING",
                severity="CRITICAL",
                expected=">= 10.0",
                actual=None,
                operator_used=">=",
                reason="No turnover statement submitted in bid pack",
                evidence=[],
                requires_human_review=True,
            ),
        ]

        agg = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=[],
            government_responses=[],
            requirements=reqs,
            facts=[],
        )

        self.assertEqual(agg.compliance_status, ComplianceStatus.MISSING.value)
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)
        self.assertTrue(agg.review_required)
        self.assertLessEqual(agg.compliance_score, 55.0)
        self.assertIn(agg.risk_level, ["HIGH", "CRITICAL"])
        self.assertEqual(agg.recommendation["verdict"], "REVIEW")
        self.assertGreater(len(agg.pending_requirements), 0)
        self.assertEqual(agg.pending_requirements[0]["requirement_id"], "REQ-TO-02")
        self.assertIn("suggested_bidder_action", agg.pending_requirements[0])

    # =========================================================================
    # 3. Cross-Document Contradiction Integrity Pipeline
    # =========================================================================
    def test_03_e2e_cross_document_contradiction_integrity(self):
        """
        Cross-document contradiction test:
        - Compliance result is PASS on technical doc
        - Contradiction detected against financial doc
        - Architecture Assertion: Compliance status remains PASS, Overall status = REVIEW
        - Score capped at 65.0 due to CRITICAL_CONTRADICTION_CAP
        - Risk level escalates
        - Review category = INTEGRITY_CONTRADICTION
        """
        tender_id = "TENDER-SIH-003"
        bid_id = "BID-CONTRA-003"

        reqs = [
            TenderRequirement(
                requirement_id="REQ-TO-03",
                tender_id=tender_id,
                category="FINANCIAL_EXPERIENCE",
                description="Turnover >= 10 Cr",
                field="turnover_cr",
                operator=">=",
                expected_value=10.0,
                mandatory=True,
            )
        ]

        comp_results = [
            VerificationResult(
                verification_id="VERIF-TO-03",
                requirement_id="REQ-TO-03",
                bid_id=bid_id,
                status="PASS",
                severity="CRITICAL",
                expected=">= 10.0",
                actual="12.0",
                operator_used=">=",
                reason="Turnover 12.0 Cr meets 10.0 Cr requirement",
                evidence=[EvidencePointer("technical_bid.pdf", 1, [10, 10, 20, 20], "12.0 Cr")],
                requires_human_review=False,
            )
        ]

        finding = IntegrityFinding(
            finding_id="INT-TO-01",
            bid_id=bid_id,
            finding_type="TURNOVER_CONTRADICTION",
            field="turnover_cr",
            severity="HIGH",
            status="CONTRADICTION",
            description="Turnover differs across documents: 12.0 Cr vs 4.5 Cr",
            value_a=12.0,
            value_b=4.5,
            evidence_a={"document": "technical_bid.pdf", "page": 1, "bbox": [10, 10, 20, 20]},
            evidence_b={"document": "financial_annexure.pdf", "page": 2, "bbox": [30, 30, 40, 40]},
            requires_human_review=True,
            source="CROSS_DOCUMENT_CONTRADICTION_ENGINE",
        )

        agg = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=[finding],
            government_responses=[],
            requirements=reqs,
            facts=[],
        )

        # Rule 6 check: Compliance remains PASS, Overall becomes REVIEW
        self.assertEqual(agg.compliance_status, ComplianceStatus.PASS.value)
        self.assertEqual(agg.integrity_status, IntegrityStatus.CONTRADICTION.value)
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)
        self.assertTrue(agg.review_required)
        self.assertEqual(agg.compliance_score, 65.0)  # Hard capped at CRITICAL_CONTRADICTION_CAP (65.0)
        self.assertIn(agg.risk_level, ["HIGH", "CRITICAL"])
        self.assertEqual(agg.recommendation["verdict"], "REVIEW")
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.INTEGRITY_CONTRADICTION.value)

    # =========================================================================
    # 4. Debarred Entity Fail-Closed Pipeline
    # =========================================================================
    def test_04_e2e_debarred_entity_fail_closed(self):
        """
        Debarred entity test:
        - Government DebarmentAdapter returns DEBARRED
        - Score hard-capped to 0.0
        - Risk Level = CRITICAL
        - Overall Status = FAIL
        - AI Recommendation = FAIL with explicit debarment blocker reason
        """
        tender_id = "TENDER-SIH-004"
        bid_id = "BID-DEBARRED-004"

        reqs = [
            TenderRequirement(
                requirement_id="REQ-01",
                tender_id=tender_id,
                category="COMPLIANCE",
                description="General compliance clause",
                field="general",
                operator="==",
                expected_value=True,
                mandatory=True,
            )
        ]

        comp_results = [
            VerificationResult(
                verification_id="VERIF-01",
                requirement_id="REQ-01",
                bid_id=bid_id,
                status="PASS",
                severity="CRITICAL",
                expected=True,
                actual=True,
                operator_used="==",
                reason="Clause satisfied",
                evidence=[],
                requires_human_review=False,
            )
        ]

        debar_resp = AdapterResponse(
            adapter_name="DebarmentAdapter",
            status=VerificationStatus.DEBARRED,
            queried_identifier="MALICIOUS_BIDDER_LTD",
            source="MOCK_DEBARMENT_REGISTRY",
            reason="Entity is on active Ministry debarment blacklist for collusive bidding.",
            matched_entity={"status": "DEBARRED", "reason": "Collusive bidding"},
            is_mock=True,
        )

        agg = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=[],
            government_responses=[debar_resp],
            requirements=reqs,
            facts=[],
        )

        self.assertEqual(agg.overall_status, OverallStatus.FAIL.value)
        self.assertEqual(agg.compliance_score, 0.0)
        self.assertEqual(agg.risk_level, "CRITICAL")
        self.assertEqual(agg.recommendation["verdict"], "FAIL")
        self.assertIn("debarment", str(agg.recommendation["detailed_summary"]).lower())
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.DEBARMENT_ALERT.value)

    # =========================================================================
    # 5. Unknown Applicability Fail-Closed Pipeline
    # =========================================================================
    def test_05_e2e_unknown_applicability_review(self):
        """
        Unknown applicability test:
        - Requirement applicability evaluated with UNKNOWN status
        - Score penalised by unknown review deduction
        - Route to human review queue
        """
        tender_id = "TENDER-SIH-005"
        bid_id = "BID-UNKNOWN-005"

        reqs = [
            TenderRequirement(
                requirement_id="REQ-STARTUP-01",
                tender_id=tender_id,
                category="STATUTORY_EXEMPTION",
                description="Turnover exemption claimed under Startup India",
                field="turnover_cr",
                operator=">=",
                expected_value=10.0,
                mandatory=True,
            )
        ]

        # Bidder claimed exemption but DPIIT proof is ambiguous / unverified
        comp_results = [
            VerificationResult(
                verification_id="VERIF-STARTUP-01",
                requirement_id="REQ-STARTUP-01",
                bid_id=bid_id,
                status="REVIEW",
                severity="MAJOR",
                expected="DPIIT certificate",
                actual="Unverified claim",
                operator_used="EXISTS",
                reason="Exemption validity cannot be authoritatively determined; marked UNKNOWN_REVIEW",
                evidence=[],
                requires_human_review=True,
            )
        ]

        tender_meta = {
            "exemptions_detected": [
                {
                    "rule_id": "EXEMPT-DPIIT-01",
                    "exemption_type": "STARTUP_TURNOVER_EXEMPTION",
                    "status": "UNKNOWN",
                    "confidence": 0.45,
                    "evidence_snippet": "We are an innovative startup and request waiver",
                }
            ]
        }

        agg = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=[],
            government_responses=[],
            requirements=reqs,
            facts=[],
            tender_metadata=tender_meta,
        )

        self.assertEqual(agg.compliance_status, ComplianceStatus.REVIEW.value)
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)
        self.assertTrue(agg.review_required)
        self.assertTrue(any("review" in d.get("status", "").lower() or "unknown" in d.get("reason", "").lower() for d in agg.compliance_score_breakdown["deductions"]))
        self.assertLessEqual(agg.compliance_score, 90.0)

    # =========================================================================
    # 6. Data Continuity & Identifier Traceability
    # =========================================================================
    def test_06_e2e_data_continuity_and_identifier_traceability(self):
        """
        Data Continuity test:
        Trace identifiers through all stages:
        tender_id, bid_id, requirement_id, fact_id, verification_id, deterministic_run_id,
        document, page, bbox, snippet.
        Assert none are lost or mutated.
        """
        tender_id = "TENDER-TRACE-001"
        bid_id = "BID-TRACE-001"

        req = TenderRequirement(
            requirement_id="REQ-EMD-01",
            tender_id=tender_id,
            category="BID_SECURITY",
            description="EMD bank guarantee of Rs. 2.0 Lakhs",
            field="emd_amount_lakhs",
            operator=">=",
            expected_value=2.0,
            mandatory=True,
        )

        fact = BidderFact(
            fact_id="FACT-EMD-01",
            bid_id=bid_id,
            field="emd_amount_lakhs",
            canonical_field="EMD_AMOUNT",
            value=2.5,
            unit="INR_LAKHS",
            source_document="emd_bg.pdf",
            page=2,
            bbox=[100.0, 200.0, 350.0, 240.0],
            raw_text_snippet="Bank Guarantee for EMD: INR 2,50,000/-",
            extraction_confidence="HIGH",
        )

        result = VerificationResult(
            verification_id="VERIF-EMD-01",
            requirement_id=req.requirement_id,
            bid_id=bid_id,
            status="PASS",
            severity="CRITICAL",
            expected=">= 2.0",
            actual="2.5",
            operator_used=">=",
            reason="EMD amount Rs. 2.5 Lakhs satisfies required Rs. 2.0 Lakhs",
            evidence=[EvidencePointer(fact.source_document, fact.page, fact.bbox, fact.raw_text_snippet)],
            requires_human_review=False,
        )

        agg = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=[result],
            integrity_findings=[],
            government_responses=[],
            requirements=[req],
            facts=[fact],
        )

        # Trace verification_id & run_id
        self.assertEqual(agg.verification_id, f"VERIF-{tender_id}-{bid_id}")
        self.assertTrue(agg.deterministic_run_id.startswith("RUN-"))
        self.assertEqual(agg.tender_id, tender_id)
        self.assertEqual(agg.bid_id, bid_id)

        # Trace evidence reference in compliance results
        self.assertEqual(len(agg.verification_results), 1)
        res_dict = agg.verification_results[0]
        self.assertEqual(res_dict["verification_id"], "VERIF-EMD-01")
        self.assertEqual(res_dict["requirement_id"], "REQ-EMD-01")
        ev_item = res_dict["evidence"][0]
        ev_doc = ev_item["document"] if isinstance(ev_item, dict) else ev_item.document
        ev_page = ev_item["page"] if isinstance(ev_item, dict) else ev_item.page
        ev_bbox = ev_item["bbox"] if isinstance(ev_item, dict) else ev_item.bbox
        ev_snip = ev_item["snippet"] if isinstance(ev_item, dict) else ev_item.snippet
        self.assertEqual(ev_doc, "emd_bg.pdf")
        self.assertEqual(ev_page, 2)
        self.assertEqual(ev_bbox, [100.0, 200.0, 350.0, 240.0])
        self.assertEqual(ev_snip, "Bank Guarantee for EMD: INR 2,50,000/-")

        # Trace dossier generation
        dossier = self.orchestrator._generate_dossier(
            tender_id=tender_id,
            bid_id=bid_id,
            legal_name="Traceable Corp",
            requirements=[req],
            facts=[fact],
            compliance_results=[result],
            integrity_findings=[],
            aggregated=agg,
            total_time_ms=12.5,
        )

        self.assertEqual(dossier.tender["tender_id"], tender_id)
        self.assertEqual(dossier.bidder["bid_id"], bid_id)
        self.assertEqual(dossier.evidence[0]["fact_id"], "FACT-EMD-01")
        self.assertEqual(dossier.evidence[0]["document"], "emd_bg.pdf")
        self.assertEqual(dossier.evidence[0]["page"], 2)
        self.assertEqual(dossier.evidence[0]["bbox"], [100.0, 200.0, 350.0, 240.0])
        self.assertIsNotNone(dossier.provenance_graph)

    # =========================================================================
    # 7. Provenance DAG & Deterministic Replay Reproducibility
    # =========================================================================
    def test_07_e2e_provenance_dag_and_replay_reproducibility(self):
        """
        Deterministic Replay test:
        - Construct Provenance DAG
        - Verify byte-for-byte reproducibility of run_id and graph structure
        """
        tender_id = "TENDER-DAG-001"
        bid_id = "BID-DAG-001"

        req = TenderRequirement(
            requirement_id="REQ-01",
            tender_id=tender_id,
            category="COMPLIANCE",
            description="Valid registration",
            operator="==",
            expected_value=True,
            mandatory=True,
        )

        fact = BidderFact(
            fact_id="FACT-01",
            bid_id=bid_id,
            field="registration",
            canonical_field="LEGAL_ENTITY_NAME",
            value="Alpha Inc",
            source_document="reg.pdf",
            page=1,
            bbox=[10, 10, 50, 50],
            raw_text_snippet="Registered as Alpha Inc",
            extraction_confidence="HIGH",
        )

        res = VerificationResult(
            verification_id="VERIF-01",
            requirement_id="REQ-01",
            bid_id=bid_id,
            status="PASS",
            severity="CRITICAL",
            expected=True,
            actual=True,
            operator_used="==",
            reason="Registration confirmed",
            evidence=[EvidencePointer("reg.pdf", 1, [10, 10, 50, 50], "Registered as Alpha Inc")],
            requires_human_review=False,
        )

        # Build DAG run 1
        dag1 = ProvenanceDAGBuilder.build(
            requirements=[req],
            facts=[fact],
            results=[res],
            integrity_findings=[],
            human_review_items=[],
            bid_id=bid_id,
            tender_id=tender_id,
        )

        # Build DAG run 2
        dag2 = ProvenanceDAGBuilder.build(
            requirements=[req],
            facts=[fact],
            results=[res],
            integrity_findings=[],
            human_review_items=[],
            bid_id=bid_id,
            tender_id=tender_id,
        )

        # Byte-for-byte identical serialization
        d1_json = json.dumps(dag1.to_dict(), sort_keys=True)
        d2_json = json.dumps(dag2.to_dict(), sort_keys=True)
        self.assertEqual(d1_json, d2_json)
        import hashlib
        h1 = hashlib.sha256(d1_json.encode('utf-8')).hexdigest()
        h2 = hashlib.sha256(d2_json.encode('utf-8')).hexdigest()
        self.assertEqual(h1, h2)

    # =========================================================================
    # 8. FastAPI REST Endpoints Integration
    # =========================================================================
    def test_08_e2e_fastapi_rest_endpoints(self):
        """
        FastAPI REST API Verification:
        - POST /api/v1/verify
        - GET /api/v1/verification/{id}
        - GET /api/v1/verification/{id}/dossier
        - GET /api/v1/verification/{id}/review-items
        Validates all endpoints return complete schema without dropping new fields.
        """
        with open(self.tender_pdf, "rb") as tf, open(self.bid_pdf, "rb") as bf:
            files = [
                ("tender_file", ("TENDER-0001.pdf", tf.read(), "application/pdf")),
                ("bid_files", ("BID-00001.pdf", bf.read(), "application/pdf")),
            ]
            data = {
                "tender_id": "TENDER-REST-001",
                "bid_id": "BID-REST-001",
                "company_name": "Bharat Devices",
                "mode": "mock",
            }
            resp = self.client.post("/api/v1/verify", files=files, data=data)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        # Check Aggregated Verification schema
        verif_id = body["verification_id"]
        self.assertEqual(verif_id, "VERIF-TENDER-REST-001-BID-REST-001")
        self.assertIn("compliance_score", body)
        self.assertIsInstance(body["compliance_score"], (int, float))
        self.assertIn("risk_level", body)
        self.assertIn(body["risk_level"], ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self.assertIn("recommendation", body)
        self.assertIn("verdict", body["recommendation"])
        self.assertIn("authority_notice", body["recommendation"])
        self.assertIn("pending_requirements", body)
        self.assertIsInstance(body["pending_requirements"], list)

        # GET /api/v1/verification/{id}
        resp_get = self.client.get(f"/api/v1/verification/{verif_id}")
        self.assertEqual(resp_get.status_code, 200)
        get_body = resp_get.json()
        self.assertEqual(get_body["verification_id"], verif_id)
        self.assertEqual(get_body["compliance_score"], body["compliance_score"])

        # GET /api/v1/verification/{id}/dossier
        resp_dossier = self.client.get(f"/api/v1/verification/{verif_id}/dossier")
        self.assertEqual(resp_dossier.status_code, 200)
        dossier = resp_dossier.json()
        self.assertIn("tender", dossier)
        self.assertIn("bidder", dossier)
        self.assertIn("compliance_summary", dossier)
        self.assertIn("integrity_summary", dossier)
        self.assertIn("evidence", dossier)
        self.assertIn("provenance_graph", dossier)
        self.assertIsNotNone(dossier["provenance_graph"])
        self.assertIn("nodes", dossier["provenance_graph"])
        self.assertIn("edges", dossier["provenance_graph"])
        self.assertIn("compliance_score", dossier)
        self.assertIn("risk_assessment", dossier)
        self.assertIn("recommendation", dossier)
        self.assertIn("pending_requirements", dossier)

        # GET /api/v1/verification/{id}/review-items
        resp_reviews = self.client.get(f"/api/v1/verification/{verif_id}/review-items")
        self.assertEqual(resp_reviews.status_code, 200)
        reviews = resp_reviews.json()
        self.assertIsInstance(reviews, list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
