# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from decimal import Decimal
import json
import os
import unittest

sys.path.insert(0, os.path.abspath("."))

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    TenderRequirement,
    VerificationResult,
)
from backend.core.rule_engine import DeterministicRuleEngine
from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.verification.models import (
    AdapterResponse,
    IntegrityFinding,
    VerificationStatus,
)
from backend.verification.mock_gst import MockGSTAdapter
from backend.verification.mock_pan import MockPANAdapter
from backend.verification.mock_udyam import MockUdyamAdapter
from backend.verification.mock_debarment import MockDebarmentAdapter
from backend.verification.registry import MockGovernmentRegistry

class TestStep5VerificationAndContradictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MockGovernmentRegistry.get_instance()
        cls.gst_adapter = MockGSTAdapter(cls.registry)
        cls.pan_adapter = MockPANAdapter(cls.registry)
        cls.udyam_adapter = MockUdyamAdapter(cls.registry)
        cls.debarment_adapter = MockDebarmentAdapter(cls.registry)
        cls.contra_engine = CrossDocumentContradictionEngine()
        cls.rule_engine = DeterministicRuleEngine()

    # ==================== GOVERNMENT ADAPTER TESTS ====================

    def test_01_gstin_verified_identity_matches(self):
        # Known entity in SIH entities.jsonl: "Bharat Devices" with "29SYNTH0000003F1Z"
        res = self.gst_adapter.verify("29SYNTH0000003F1Z", expected_entity_name="Bharat Devices")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.registered_entity_name, "Bharat Devices")
        self.assertTrue(res.is_mock)
        self.assertEqual(res.source, "MOCK_GST_REGISTRY")

    def test_02_gstin_not_found(self):
        res = self.gst_adapter.verify("99UNKNOWN000000X9Z")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)
        self.assertIn("not found", res.reason)

    def test_03_gstin_identity_mismatch(self):
        # Registered to Bharat Devices, but claimed by Wrong Company
        res = self.gst_adapter.verify("29SYNTH0000003F1Z", expected_entity_name="Completely Fraudulent Corp")
        self.assertEqual(res.status, VerificationStatus.IDENTITY_MISMATCH)
        self.assertIn("does not match", res.reason)

    def test_04_pan_valid(self):
        # Known entity: "SYNTH0003F" registered to "Bharat Devices"
        res = self.pan_adapter.verify("SYNTH0003F", expected_entity_name="Bharat Devices")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_PAN_REGISTRY")

    def test_05_pan_mismatch(self):
        res = self.pan_adapter.verify("SYNTH0003F", expected_entity_name="Unrelated Bidder Pvt Ltd")
        self.assertEqual(res.status, VerificationStatus.IDENTITY_MISMATCH)

    def test_06_udyam_verified(self):
        # Known certificate in certificates.jsonl: "CERT953698" for "Bharat Devices"
        res = self.udyam_adapter.verify("CERT953698", expected_entity_name="Bharat Devices")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_UDYAM_REGISTRY")
        self.assertTrue(res.evidence[0]["is_mse"])

    def test_07_udyam_missing(self):
        res = self.udyam_adapter.verify("UDYAM-FAKE-000000")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)
        self.assertIn("not found", res.reason)

    def test_08_debarred_bidder(self):
        # Controlled debarred fixture: "Fraudulent Tech Supplies Pvt Ltd" / "DEBAR0001D"
        res = self.debarment_adapter.verify("DEBAR0001D", expected_entity_name="Fraudulent Tech Supplies Pvt Ltd")
        self.assertEqual(res.status, VerificationStatus.DEBARRED)
        self.assertIn("bid rigging", res.reason)
        self.assertEqual(res.source, "MOCK_DEBARMENT_REGISTRY")

    def test_09_non_debarred_bidder(self):
        res = self.debarment_adapter.verify("SYNTH0003F", expected_entity_name="Bharat Devices")
        self.assertEqual(res.status, VerificationStatus.NOT_DEBARRED)
        self.assertEqual(res.source, "MOCK_DEBARMENT_REGISTRY")

    # ==================== CONTRADICTION TESTS ====================

    def test_10_same_gstin_no_contradiction(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-10",
            bid_id="BID-01",
            field_name="gstin",
            value_a="29SYNTH0000003F1Z",
            value_b="29SYNTH0000003F1Z",
            document_a="tech_bid.pdf",
            page_a=2,
            document_b="annexure.pdf",
            page_b=4,
        )
        self.assertEqual(finding.status, "CONSISTENT")
        self.assertFalse(finding.requires_human_review)

    def test_11_different_gstin_contradiction(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-11",
            bid_id="BID-01",
            field_name="gstin",
            value_a="29SYNTH0000003F1Z",
            value_b="29SYNTH0000103F1Z",
            document_a="tech_bid.pdf",
            page_a=2,
            document_b="annexure.pdf",
            page_b=4,
        )
        self.assertEqual(finding.status, "CONTRADICTION")
        self.assertEqual(finding.severity, "HIGH")
        self.assertTrue(finding.requires_human_review)

    def test_12_same_pan_no_contradiction(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-12",
            bid_id="BID-01",
            field_name="pan",
            value_a="SYNTH0003F",
            value_b="SYNTH0003F",
            document_a="tech.pdf",
            page_a=1,
            document_b="pan_copy.pdf",
            page_b=1,
        )
        self.assertEqual(finding.status, "CONSISTENT")

    def test_13_different_pan_contradiction(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-13",
            bid_id="BID-01",
            field_name="pan",
            value_a="SYNTH0003F",
            value_b="SYNTH9999X",
            document_a="tech.pdf",
            page_a=1,
            document_b="declaration.pdf",
            page_b=2,
        )
        self.assertEqual(finding.status, "CONTRADICTION")
        self.assertEqual(finding.severity, "HIGH")

    def test_14_equivalent_company_name_formatting(self):
        # Legal suffix formatting: "Asterion Systems Pvt Ltd" vs "Asterion Systems PVT. LTD."
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-14",
            bid_id="BID-02",
            field_name="company_name",
            value_a="Asterion Systems Pvt Ltd",
            value_b="Asterion Systems PVT. LTD.",
            document_a="doc_a.pdf",
            page_a=1,
            document_b="doc_b.pdf",
            page_b=1,
        )
        self.assertEqual(finding.status, "CONSISTENT")
        self.assertFalse(finding.requires_human_review)

    def test_15_material_company_name_mismatch(self):
        # Expansion / alias difference: "Asterion Systems Pvt Ltd" vs "Asterion Systems Private Limited Operations"
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-15",
            bid_id="BID-02",
            field_name="company_name",
            value_a="Asterion Systems Pvt Ltd",
            value_b="Asterion Systems Private Limited Operations",
            document_a="doc_a.pdf",
            page_a=1,
            document_b="doc_b.pdf",
            page_b=3,
        )
        self.assertEqual(finding.status, "REVIEW")
        self.assertEqual(finding.severity, "MEDIUM")
        self.assertTrue(finding.requires_human_review)

    def test_16_different_warranty_values(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-16",
            bid_id="BID-03",
            field_name="warranty",
            value_a="5 years",
            value_b="3 years",
            document_a="spec.pdf",
            page_a=12,
            document_b="oem.pdf",
            page_b=4,
        )
        self.assertEqual(finding.status, "CONTRADICTION")
        self.assertEqual(finding.severity, "HIGH")

    def test_17_equivalent_normalized_monetary_values(self):
        # ₹12.24 crore vs INR 122400000
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-17",
            bid_id="BID-04",
            field_name="turnover",
            value_a="₹12.24 crore",
            value_b="INR 122400000",
            document_a="ca_cert.pdf",
            page_a=1,
            document_b="balance_sheet.pdf",
            page_b=10,
        )
        self.assertEqual(finding.status, "CONSISTENT")
        self.assertFalse(finding.requires_human_review)

    def test_18_different_turnover_values(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-18",
            bid_id="BID-04",
            field_name="turnover",
            value_a="12.24 crore",
            value_b="17.02 crore",
            document_a="tech_bid.pdf",
            page_a=3,
            document_b="ca_cert.pdf",
            page_b=1,
        )
        self.assertEqual(finding.status, "CONTRADICTION")
        self.assertEqual(finding.severity, "HIGH")

    def test_19_missing_second_side_evidence(self):
        # Incomplete evidence: Document B is missing
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-19",
            bid_id="BID-05",
            field_name="oem_authorization",
            value_a="Authorized Partner",
            value_b=None,
            document_a="declaration.pdf",
            page_a=5,
            document_b="",
            page_b=1,
        )
        self.assertEqual(finding.status, "REVIEW")
        self.assertEqual(finding.finding_type, "INCOMPLETE_EVIDENCE")
        self.assertTrue(finding.requires_human_review)

    def test_20_evidence_from_both_documents_preserved(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="TEST-20",
            bid_id="BID-06",
            field_name="gstin",
            value_a="29SYNTH0000003F1Z",
            value_b="29SYNTH0000103F1Z",
            document_a="technical_bid.pdf",
            page_a=10,
            bbox_a=[50.0, 60.0, 150.0, 200.0],
            snippet_a="GSTIN: 29SYNTH0000003F1Z declared in technical proposal.",
            document_b="annexure_iv.pdf",
            page_b=8,
            bbox_b=[80.0, 90.0, 180.0, 250.0],
            snippet_b="Supplier GSTIN: 29SYNTH0000103F1Z.",
        )
        self.assertEqual(finding.evidence_a["document"], "technical_bid.pdf")
        self.assertEqual(finding.evidence_a["page"], 10)
        self.assertEqual(finding.evidence_a["bbox"], [50.0, 60.0, 150.0, 200.0])
        self.assertIn("29SYNTH0000003F1Z", finding.evidence_a["snippet"])

        self.assertEqual(finding.evidence_b["document"], "annexure_iv.pdf")
        self.assertEqual(finding.evidence_b["page"], 8)
        self.assertEqual(finding.evidence_b["bbox"], [80.0, 90.0, 180.0, 250.0])
        self.assertIn("29SYNTH0000103F1Z", finding.evidence_b["snippet"])

    # ==================== COMPLIANCE / INTEGRITY SEPARATION ====================

    def test_21_compliance_pass_with_integrity_contradiction(self):
        """
        CRITICAL ARCHITECTURAL TEST:
        Compliance asks: Does the bidder meet the tender requirement?
        Integrity asks: Is there cross-document inconsistency?
        Compliance PASS must NEVER be silently mutated to FAIL because of an integrity finding.
        """
        # Requirement: Turnover >= 10 Crore
        req = TenderRequirement(
            requirement_id="REQ-TO-10CR",
            tender_id="TENDER-01",
            category="FINANCIAL_CAPACITY",
            description="Turnover >= 10 Crore",
            field="turnover_cr",
            operator=">=",
            expected_value=10.0,
        )
        # Bidder facts: Technical bid says 12.24 Cr (meets 10 Cr!), CA cert says 17.02 Cr (also meets 10 Cr!)
        fact_tech = BidderFact(
            fact_id="F-TO-01",
            bid_id="BID-SEP-01",
            field="turnover_cr",
            value=12.24,
            source_document="tech_bid.pdf",
            page=3,
        )
        fact_ca = BidderFact(
            fact_id="F-TO-02",
            bid_id="BID-SEP-01",
            field="turnover_cr",
            value=17.02,
            source_document="ca_cert.pdf",
            page=1,
        )

        # 1. Compliance verification
        verif_results = self.rule_engine.verify_bid([req], [fact_tech])
        self.assertEqual(verif_results[0].status, ComplianceStatus.PASS.value)
        self.assertEqual(float(verif_results[0].actual), 12.24)

        # 2. Integrity contradiction check
        contra_findings = self.contra_engine.detect_contradictions_in_bid("BID-SEP-01", [fact_tech, fact_ca])
        self.assertEqual(len(contra_findings), 1)
        self.assertEqual(contra_findings[0].status, "CONTRADICTION")

        # 3. Verify separation: Compliance remains PASS!
        self.assertEqual(verif_results[0].status, ComplianceStatus.PASS.value)
        self.assertNotEqual(verif_results[0].status, ComplianceStatus.FAIL.value)

    def test_22_compliance_fail_without_integrity_issue(self):
        req = TenderRequirement(
            requirement_id="REQ-WAR-5Y",
            tender_id="TENDER-01",
            category="TECHNICAL",
            description="Warranty >= 5 years",
            field="warranty_years",
            operator=">=",
            expected_value=5,
        )
        fact_war1 = BidderFact(
            fact_id="F-W1", bid_id="BID-SEP-02", field="warranty_years", value=3,
            source_document="tech.pdf", page=1
        )
        fact_war2 = BidderFact(
            fact_id="F-W2", bid_id="BID-SEP-02", field="warranty_years", value=3,
            source_document="oem.pdf", page=2
        )

        # Compliance fails (3 < 5)
        verif_results = self.rule_engine.verify_bid([req], [fact_war1])
        self.assertEqual(verif_results[0].status, ComplianceStatus.FAIL.value)

        # Integrity is clean (both state 3 years)
        contra_findings = self.contra_engine.detect_contradictions_in_bid("BID-SEP-02", [fact_war1, fact_war2])
        self.assertEqual(len(contra_findings), 0)

    def test_23_integrity_anomaly_never_silently_changes_compliance(self):
        # VerificationResult status enum has NO "FRAUD" or "ANOMALOUS" value
        self.assertNotIn("FRAUD", [s.value for s in ComplianceStatus])
        self.assertNotIn("SUSPICIOUS", [s.value for s in ComplianceStatus])

    # ==================== PROVENANCE TESTS ====================

    def test_24_mock_adapter_identifies_mock_source(self):
        gst_res = self.gst_adapter.verify("29SYNTH0000003F1Z")
        self.assertTrue(gst_res.is_mock)
        self.assertEqual(gst_res.source, "MOCK_GST_REGISTRY")

        pan_res = self.pan_adapter.verify("SYNTH0003F")
        self.assertTrue(pan_res.is_mock)
        self.assertEqual(pan_res.source, "MOCK_PAN_REGISTRY")

        udyam_res = self.udyam_adapter.verify("CERT953698")
        self.assertTrue(udyam_res.is_mock)
        self.assertEqual(udyam_res.source, "MOCK_UDYAM_REGISTRY")

        deb_res = self.debarment_adapter.verify("DEBAR0001D")
        self.assertTrue(deb_res.is_mock)
        self.assertEqual(deb_res.source, "MOCK_DEBARMENT_REGISTRY")

    def test_25_no_result_claims_live_government_verification(self):
        adapters = [self.gst_adapter, self.pan_adapter, self.udyam_adapter, self.debarment_adapter]
        for adapter in adapters:
            self.assertTrue(adapter.source_name.startswith("MOCK_"))

    # ==================== DETERMINISM TESTS ====================

    def test_26_same_input_repeated_three_times_identical(self):
        runs = []
        for _ in range(3):
            finding = self.contra_engine.evaluate_pair(
                contradiction_id="TEST-DET",
                bid_id="BID-DET",
                field_name="turnover_cr",
                value_a="12.24",
                value_b="17.02",
                document_a="doc_a.pdf",
                page_a=1,
                snippet_a="turnover 12.24 crore",
                document_b="doc_b.pdf",
                page_b=5,
                snippet_b="turnover 17.02 crore",
            )
            runs.append(json.dumps(finding.to_dict(), sort_keys=True))

        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])

if __name__ == "__main__":
    unittest.main(verbosity=2)
