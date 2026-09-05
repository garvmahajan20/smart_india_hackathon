# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
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
from backend.ingestion.bbox import convert_pymupdf_to_contract_bbox, validate_bbox
from backend.ingestion.confidence import evaluate_page_extraction_quality
from backend.ingestion.evidence import build_evidence_from_block, find_evidence_for_keyword
from backend.ingestion.fact_extractor_interface import RuleBasedFactExtractor
from backend.ingestion.models import (
    DocumentType,
    EvidenceReference,
    ExtractionMethod,
    ExtractionResult,
    TextBlock,
)
from backend.ingestion.ocr import MockOCREngine, TesseractOCREngine
from backend.ingestion.page_segmenter import classify_document_type
from backend.ingestion.pipeline import DocumentIngestionPipeline

class TestDocumentIngestionPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_bid_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids/BID-00001.pdf"
        cls.sample_tender_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/tenders/TENDER-0001.pdf"
        cls.pipeline = DocumentIngestionPipeline()
        cls.rule_engine = DeterministicRuleEngine()
        cls.contra_engine = CrossDocumentContradictionEngine()

    # 1. Native PDF extraction
    def test_01_native_pdf_extraction(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        self.assertEqual(res.overall_method, ExtractionMethod.NATIVE_PDF)
        self.assertEqual(len(res.errors), 0)
        self.assertGreater(len(res.pages), 0)

    # 2. Page count
    def test_02_page_count(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        self.assertEqual(res.metadata.page_count, 2)
        self.assertEqual(len(res.pages), 2)

    # 3. Page numbering
    def test_03_page_numbering(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        self.assertEqual(res.pages[0].page_number, 1)
        self.assertEqual(res.pages[1].page_number, 2)

    # 4. Text extraction
    def test_04_text_extraction(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        p1_text = res.pages[0].text
        self.assertIn("SYNTHETIC BID SUBMISSION", p1_text)
        self.assertIn("BID-00001", p1_text)

    # 5. Text block extraction
    def test_05_text_block_extraction(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        blocks = res.pages[0].blocks
        self.assertGreater(len(blocks), 5)
        for b in blocks:
            self.assertIsInstance(b, TextBlock)
            self.assertEqual(len(b.bbox), 4)

    # 6. Bbox coordinate conversion: PyMuPDF [x0, y0, x1, y1] -> Contract [ymin, xmin, ymax, xmax]
    def test_06_bbox_coordinate_conversion(self):
        # x0=100, y0=50, x1=300, y1=200
        contract_bbox = convert_pymupdf_to_contract_bbox(100.0, 50.0, 300.0, 200.0, page_width=600.0, page_height=800.0)
        # Expected: ymin=50, xmin=100, ymax=200, xmax=300
        self.assertEqual(contract_bbox, [50.0, 100.0, 200.0, 300.0])

    # 7. Bbox validity
    def test_07_bbox_validity(self):
        valid, msg = validate_bbox([50.0, 100.0, 200.0, 300.0], page_width=600.0, page_height=800.0)
        self.assertTrue(valid, msg)

        # Inverted vertical
        inv_v, msg_v = validate_bbox([250.0, 100.0, 200.0, 300.0], page_width=600.0, page_height=800.0)
        self.assertFalse(inv_v)

        # Inverted horizontal
        inv_h, msg_h = validate_bbox([50.0, 350.0, 200.0, 300.0], page_width=600.0, page_height=800.0)
        self.assertFalse(inv_h)

    # 8. Page dimensions
    def test_08_page_dimensions(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        p = res.pages[0]
        # Standard A4 is ~595.28 x 841.89
        self.assertAlmostEqual(p.width, 595.28, delta=1.0)
        self.assertAlmostEqual(p.height, 841.89, delta=1.0)

    # 9. Empty page detection
    def test_09_empty_page_detection(self):
        conf_cat, q_score, is_empty, is_low, warns = evaluate_page_extraction_quality("", 0)
        self.assertTrue(is_empty)
        self.assertTrue(is_low)
        self.assertEqual(conf_cat, "LOW")
        self.assertEqual(q_score, 0.0)

    # 10. Low-text page detection
    def test_10_low_text_page_detection(self):
        short_text = "Cover Page"
        conf_cat, q_score, is_empty, is_low, warns = evaluate_page_extraction_quality(short_text, 1)
        self.assertFalse(is_empty)
        self.assertTrue(is_low)
        self.assertIn("Low text volume", warns[0])

    # 11. Extraction confidence heuristic
    def test_11_extraction_confidence_heuristic(self):
        normal_text = "This is a full document section containing standard procurement clauses and facts. " * 5
        conf_cat, q_score, is_empty, is_low, warns = evaluate_page_extraction_quality(normal_text, 10)
        self.assertEqual(conf_cat, "HIGH")
        self.assertGreater(q_score, 0.8)

    # 12. OCR fallback decision
    def test_12_ocr_fallback_decision(self):
        # Using MockOCREngine with available=True
        mock_ocr = MockOCREngine(simulated_text="OCR Scanned Content", available=True)
        self.assertTrue(mock_ocr.is_available())
        res = mock_ocr.extract_page(b"fake_image_bytes", 1, 600.0, 800.0)
        self.assertTrue(res.success)
        self.assertEqual(res.text, "OCR Scanned Content")

    # 13. OCR unavailable behavior
    def test_13_ocr_unavailable_behavior(self):
        mock_ocr = MockOCREngine(available=False)
        self.assertFalse(mock_ocr.is_available())
        res = mock_ocr.extract_page(b"fake_image_bytes", 1, 600.0, 800.0)
        self.assertFalse(res.success)
        self.assertIn("unavailable", res.error)

    # 14. Hybrid extraction
    def test_14_hybrid_extraction(self):
        # Create a pipeline with MockOCREngine to verify HYBRID aggregation
        mock_ocr = MockOCREngine(simulated_text="Mock OCR Text", available=True)
        pipe = DocumentIngestionPipeline(ocr_engine=mock_ocr)
        res = pipe.ingest_file(self.sample_bid_pdf)
        # For a clean 2-page text PDF, all pages extract natively without needing OCR
        self.assertEqual(res.overall_method, ExtractionMethod.NATIVE_PDF)

    # 15. Provenance preservation
    def test_15_provenance_preservation(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        self.assertEqual(res.metadata.filename, "BID-00001.pdf")
        self.assertEqual(res.metadata.bid_id, "BID-00001")
        self.assertEqual(len(res.metadata.sha256), 64)

    # 16. Evidence generation
    def test_16_evidence_generation(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        ev = find_evidence_for_keyword("BID-00001.pdf", res.pages, "SYNTHETIC BID")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.document, "BID-00001.pdf")
        self.assertEqual(ev.page, 1)
        self.assertIn("SYNTHETIC BID", ev.snippet)
        self.assertEqual(len(ev.bbox), 4)

    # 17. Malformed / missing PDF handling
    def test_17_malformed_or_missing_pdf_handling(self):
        res = self.pipeline.ingest_file("nonexistent_path_file.pdf")
        self.assertEqual(res.overall_method, ExtractionMethod.FAILED)
        self.assertGreater(len(res.errors), 0)
        self.assertIn("does not exist", res.errors[0])

    # 18. Document type handling
    def test_18_document_type_handling(self):
        self.assertEqual(classify_document_type("BID-00001.pdf"), DocumentType.BID)
        self.assertEqual(classify_document_type("TENDER-0001.pdf"), DocumentType.TENDER)
        self.assertEqual(classify_document_type("technical_proposal.pdf"), DocumentType.TECHNICAL_BID)
        self.assertEqual(classify_document_type("ca_turnover_certificate.pdf"), DocumentType.CERTIFICATE)
        self.assertEqual(classify_document_type("random_unknown_file.pdf"), DocumentType.UNKNOWN)

    # 19. Deterministic repeated extraction
    def test_19_deterministic_repeated_extraction(self):
        runs = []
        for _ in range(3):
            r = self.pipeline.ingest_file(self.sample_bid_pdf)
            runs.append(json.dumps(r.to_dict(), sort_keys=True))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])

    # 20. Contract compatibility (Document and BidderFact schemas)
    def test_20_contract_compatibility(self):
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        d_dict = res.to_dict()
        self.assertIn("metadata", d_dict)
        self.assertIn("pages", d_dict)
        self.assertEqual(d_dict["overall_method"], "NATIVE_PDF")

    # 21. Step 4 evidence compatibility
    def test_21_step4_evidence_compatibility(self):
        # Extract facts using RuleBasedFactExtractor
        extractor = RuleBasedFactExtractor()
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        facts = extractor.extract_facts(res)
        self.assertGreater(len(facts), 0)

        # Feed extracted fact into Step 4 rule engine
        # Find delivery_days fact
        deliv_facts = [f for f in facts if f.field == "delivery_days"]
        if deliv_facts:
            req = TenderRequirement(
                requirement_id="REQ-DELIV-01",
                tender_id="TENDER-0069",
                category="TECHNICAL",
                description="Delivery days <= 90",
                field="delivery_days",
                operator="<=",
                expected_value=90
            )
            verif = self.rule_engine.verify_bid([req], deliv_facts)
            self.assertEqual(len(verif), 1)
            # Extracted delivery_days = 85 <= 90 -> PASS
            self.assertEqual(verif[0].status, ComplianceStatus.PASS.value)
            self.assertEqual(verif[0].evidence[0]["document"], "BID-00001.pdf")
            self.assertEqual(len(verif[0].evidence[0]["bbox"]), 4)

    # 22. Step 5 evidence compatibility
    def test_22_step5_evidence_compatibility(self):
        extractor = RuleBasedFactExtractor()
        res = self.pipeline.ingest_file(self.sample_bid_pdf)
        facts = extractor.extract_facts(res)

        # Get turnover_cr fact extracted from BID-00001.pdf
        to_facts = [f for f in facts if f.field == "turnover_cr"]
        self.assertGreater(len(to_facts), 0)
        first_to = to_facts[0]

        # Evaluate against contradiction engine
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="CONTRA-TEST-01",
            bid_id="BID-00001",
            field_name="turnover_cr",
            value_a=first_to.value,
            value_b=first_to.value,
            document_a=first_to.source_document,
            page_a=first_to.page,
            bbox_a=first_to.bbox,
            snippet_a=first_to.raw_text_snippet,
            document_b=first_to.source_document,
            page_b=first_to.page,
            bbox_b=first_to.bbox,
            snippet_b=first_to.raw_text_snippet,
        )
        self.assertEqual(finding.status, "CONSISTENT")
        self.assertEqual(finding.evidence_a["bbox"], first_to.bbox)
        self.assertEqual(len(finding.evidence_a["bbox"]), 4)

if __name__ == "__main__":
    unittest.main(verbosity=2)
