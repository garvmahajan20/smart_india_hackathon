# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import os
import unittest
import tempfile

sys.path.insert(0, os.path.abspath("."))

from backend.core.models import BidderFact, TenderRequirement, VerificationResult, EvidencePointer
from backend.extraction.mock_provider import MockLLMProvider
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

class TestStep8Orchestration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aggregator = VerificationAggregator()
        cls.orchestrator = VerificationOrchestrator(mode=LLMMode.MOCK)

    # 1. Fully compliant bid
    def test_01_fully_compliant_bid(self):
        req = VerificationResult(
            verification_id="V-01", requirement_id="REQ-01", bid_id="BID-01",
            status="PASS", severity="CRITICAL", expected=">= 10 Cr", actual="12 Cr",
            operator_used=">=", reason="Meets requirement",
            evidence=[EvidencePointer(document="doc.pdf", page=1)], requires_human_review=False
        )
        agg = self.aggregator.aggregate("T-01", "BID-01", [req], [], [])
        self.assertEqual(agg.compliance_status, ComplianceStatus.PASS.value)
        self.assertEqual(agg.integrity_status, IntegrityStatus.CONSISTENT.value)
        self.assertEqual(agg.overall_status, OverallStatus.PASS.value)
        self.assertFalse(agg.review_required)

    # 2. Non-compliant turnover
    def test_02_non_compliant_turnover(self):
        req = VerificationResult(
            verification_id="V-02", requirement_id="REQ-TO", bid_id="BID-02",
            status="FAIL", severity="CRITICAL", expected=">= 10 Cr", actual="5 Cr",
            operator_used=">=", reason="Actual turnover below threshold",
            evidence=[EvidencePointer(document="doc.pdf", page=1)], requires_human_review=False
        )
        agg = self.aggregator.aggregate("T-01", "BID-02", [req], [], [])
        self.assertEqual(agg.compliance_status, ComplianceStatus.FAIL.value)
        self.assertEqual(agg.overall_status, OverallStatus.FAIL.value)
        self.assertEqual(agg.critical_failures, 1)

    # 3. Non-compliant warranty
    def test_03_non_compliant_warranty(self):
        req = VerificationResult(
            verification_id="V-03", requirement_id="REQ-WAR", bid_id="BID-03",
            status="FAIL", severity="MAJOR", expected=">= 3 years", actual="2 years",
            operator_used=">=", reason="Warranty period insufficient",
            evidence=[EvidencePointer(document="doc.pdf", page=1)], requires_human_review=False
        )
        agg = self.aggregator.aggregate("T-01", "BID-03", [req], [], [])
        self.assertEqual(agg.compliance_status, ComplianceStatus.FAIL.value)
        self.assertEqual(agg.overall_status, OverallStatus.FAIL.value)
        self.assertEqual(agg.major_failures, 1)

    # 4. Missing evidence
    def test_04_missing_evidence(self):
        req = VerificationResult(
            verification_id="V-04", requirement_id="REQ-ISO", bid_id="BID-04",
            status="MISSING", severity="MAJOR", expected="ISO 9001", actual=None,
            operator_used="EXISTS", reason="Document not submitted",
            evidence=[], requires_human_review=True
        )
        agg = self.aggregator.aggregate("T-01", "BID-04", [req], [], [])
        self.assertEqual(agg.compliance_status, ComplianceStatus.MISSING.value)
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)
        self.assertTrue(agg.review_required)
        self.assertEqual(len(agg.human_review_items), 1)
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.MISSING_EVIDENCE.value)

    # 5. Integrity contradiction with compliance PASS
    def test_05_integrity_contradiction_with_compliance_pass(self):
        req = VerificationResult(
            verification_id="V-05", requirement_id="REQ-TO", bid_id="BID-05",
            status="PASS", severity="CRITICAL", expected=">= 10 Cr", actual="12.24 Cr",
            operator_used=">=", reason="Turnover meets threshold",
            evidence=[EvidencePointer(document="tech_bid.pdf", page=1)], requires_human_review=False
        )
        finding = IntegrityFinding(
            finding_id="INT-01", bid_id="BID-05", finding_type="TURNOVER_CONTRADICTION",
            field="turnover_cr", severity="HIGH", status="CONTRADICTION",
            description="Turnover differs across documents: 12.24 Cr vs 17.02 Cr",
            value_a=12.24, value_b=17.02,
            evidence_a={"document": "tech_bid.pdf", "page": 1, "bbox": [10, 10, 20, 20]},
            evidence_b={"document": "annexure.pdf", "page": 2, "bbox": [30, 30, 40, 40]},
            requires_human_review=True, source="CROSS_DOCUMENT_CONTRADICTION_ENGINE"
        )
        agg = self.aggregator.aggregate("T-01", "BID-05", [req], [finding], [])
        # CRITICAL ARCHITECTURAL ASSERTION: Compliance remains PASS!
        self.assertEqual(agg.compliance_status, ComplianceStatus.PASS.value)
        self.assertEqual(agg.integrity_status, IntegrityStatus.CONTRADICTION.value)
        # Overall status is REVIEW (for officer review), NOT silently FAIL!
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)
        self.assertTrue(agg.review_required)

    # 6. Government verification VERIFIED
    def test_06_government_verification_verified(self):
        resp = AdapterResponse(
            adapter_name="MockGSTAdapter", status=VerificationStatus.VERIFIED,
            queried_identifier="29SYNTH0000003F1Z", source="MOCK_GST_REGISTRY",
            reason="GSTIN active and legal name matches exactly.", matched_entity={"status": "ACTIVE"}, is_mock=True
        )
        agg = self.aggregator.aggregate("T-01", "BID-06", [], [], [resp])
        self.assertEqual(len(agg.government_checks), 1)
        self.assertEqual(agg.government_checks[0]["status"], "VERIFIED")

    # 7. Government verification NOT_FOUND
    def test_07_government_verification_not_found(self):
        resp = AdapterResponse(
            adapter_name="MockPANAdapter", status=VerificationStatus.NOT_FOUND,
            queried_identifier="UNKNOWN000F", source="MOCK_PAN_REGISTRY",
            reason="Record not found in mock government registry.", matched_entity={}, is_mock=True
        )
        agg = self.aggregator.aggregate("T-01", "BID-07", [], [], [resp])
        self.assertEqual(agg.government_checks[0]["status"], "NOT_FOUND")

    # 8. Government identity mismatch
    def test_08_government_identity_mismatch(self):
        resp = AdapterResponse(
            adapter_name="MockGSTAdapter", status=VerificationStatus.IDENTITY_MISMATCH,
            queried_identifier="29SYNTH0000003F1Z", source="MOCK_GST_REGISTRY",
            reason="Legal name mismatch: 'Alpha Tech' vs registered 'Beta Corp'", matched_entity={}, is_mock=True
        )
        agg = self.aggregator.aggregate("T-01", "BID-08", [], [], [resp])
        self.assertEqual(len(agg.human_review_items), 1)
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.GOVERNMENT_MISMATCH.value)

    # 9. Ambiguous government result -> REVIEW
    def test_09_ambiguous_government_result_review(self):
        resp = AdapterResponse(
            adapter_name="MockGSTAdapter", status=VerificationStatus.REVIEW,
            queried_identifier="29SYNTH0000003F1Z", source="MOCK_GST_REGISTRY",
            reason="Taxpayer registration is under active suspension.", matched_entity={}, is_mock=True
        )
        agg = self.aggregator.aggregate("T-01", "BID-09", [], [], [resp])
        self.assertEqual(len(agg.human_review_items), 1)
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.GOVERNMENT_MISMATCH.value)

    # 10. LLM grounding failure -> REVIEW
    def test_10_llm_grounding_failure_review(self):
        agg = self.aggregator.aggregate(
            "T-01", "BID-10", [], [], [],
            grounding_warnings=["Claimed turnover Rs. 20 Cr not grounded in source text blocks."]
        )
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)
        self.assertTrue(agg.review_required)
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.GROUNDING_FAILURE.value)

    # 11. Invalid PDF handling
    def test_11_invalid_pdf_handling(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"CORRUPTED_HEADER_NOT_A_REAL_PDF")
            invalid_path = f.name
        try:
            with self.assertRaises(ValueError):
                self.orchestrator.verify_submission(invalid_path, [invalid_path])
        finally:
            if os.path.exists(invalid_path):
                os.remove(invalid_path)

    # 12. Oversized upload logic check
    def test_12_oversized_upload_limit(self):
        from backend.api.app import MAX_FILE_SIZE_BYTES
        self.assertEqual(MAX_FILE_SIZE_BYTES, 25 * 1024 * 1024)

    # 13. Multiple documents
    def test_13_multiple_documents(self):
        tender = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/tenders/TENDER-0001.pdf"
        bid1 = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids/BID-00001.pdf"
        bid2 = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids/BID-00002.pdf"
        agg, dossier = self.orchestrator.verify_submission(tender, [bid1, bid2])
        self.assertIsNotNone(agg.verification_id)
        self.assertGreater(len(dossier.evidence), 0)

    # 14. Multi-page evidence
    def test_14_multi_page_evidence(self):
        req = VerificationResult(
            verification_id="V-14", requirement_id="REQ-MULTI", bid_id="BID-14",
            status="PASS", severity="MAJOR", expected="multi", actual="multi",
            operator_used="EXISTS", reason="Grounded across 2 pages",
            evidence=[EvidencePointer("doc.pdf", 1, [10, 10, 20, 20]), EvidencePointer("doc.pdf", 2, [30, 30, 40, 40])],
            requires_human_review=False
        )
        agg = self.aggregator.aggregate("T-01", "BID-14", [req], [], [])
        self.assertEqual(agg.evidence_count, 2)

    # 15. Empty / missing extraction handling
    def test_15_empty_extraction_handling(self):
        agg = self.aggregator.aggregate("T-01", "BID-15", [], [], [])
        self.assertEqual(agg.overall_status, OverallStatus.REVIEW.value)

    # 16. Debarred entity critical failure
    def test_16_debarred_entity_critical_failure(self):
        debar_resp = AdapterResponse(
            adapter_name="DebarmentAdapter", status=VerificationStatus.DEBARRED,
            queried_identifier="DEBAR0001D", source="MOCK_DEBARMENT_REGISTRY",
            reason="Entity is on active Ministry debarment blacklist.",
            matched_entity={"status": "DEBARRED", "reason": "Bid rigging"}, is_mock=True
        )
        req_pass = VerificationResult(
            verification_id="V-16", requirement_id="REQ-01", bid_id="BID-16",
            status="PASS", severity="CRITICAL", expected="10", actual="12",
            operator_used=">=", reason="Meets requirement",
            evidence=[EvidencePointer("doc.pdf", 1)], requires_human_review=False
        )
        agg = self.aggregator.aggregate("T-01", "BID-16", [req_pass], [], [debar_resp])
        # Even though requirement PASS, debarred bidder FAILS overall!
        self.assertEqual(agg.overall_status, OverallStatus.FAIL.value)
        self.assertTrue(agg.review_required)
        self.assertEqual(agg.human_review_items[0]["category"], ReviewCategory.DEBARMENT_ALERT.value)

    # 17. Safe error handling with missing API key
    def test_17_no_api_key_safe_fallback(self):
        prov = MockLLMProvider(canned_error="API key not configured")
        orch = VerificationOrchestrator(mode=LLMMode.MOCK, provider=prov)
        self.assertEqual(orch.mode, LLMMode.MOCK)

    # 18. Mock mode metadata
    def test_18_mock_mode_metadata(self):
        self.assertEqual(self.orchestrator.mode, LLMMode.MOCK)
        self.assertEqual(self.orchestrator.provider.provider_name, "MockProvider")

    # 19. Cached mode separation
    def test_19_cached_mode_separation(self):
        orch = VerificationOrchestrator(mode=LLMMode.CACHED)
        self.assertEqual(orch.mode, LLMMode.CACHED)

    # 20. Live mode metadata separation
    def test_20_live_mode_metadata_separation(self):
        orch = VerificationOrchestrator(mode=LLMMode.LIVE)
        self.assertEqual(orch.mode, LLMMode.LIVE)
        self.assertEqual(orch.provider.provider_name, "Gemini")
        self.assertEqual(orch.provider.model_name, "gemini-3.8-flash")

if __name__ == "__main__":
    unittest.main(verbosity=2)
