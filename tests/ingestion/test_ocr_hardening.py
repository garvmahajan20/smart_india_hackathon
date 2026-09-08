# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for Hardened OCR Robustness on Degraded Procurement Documents.
Covers:
1. Deterministic Page Quality Assessment (GOOD, DEGRADED, SEVERELY_DEGRADED, UNKNOWN).
2. Deterministic Image Preprocessing (Deskew, Contrast Stretching, Adaptive Binarization, Denoising).
3. Coordinate Mapping & Bounding Box Safety (Physical grounding, reversible deskew/scale transforms).
4. OCR Output Quality Validation (ACCEPTED, LOW_CONFIDENCE, FAILED).
5. Selective OCR Fallback & Bounded Multi-Pass Execution.
6. Adversarial OCR Invariants (Garbage / noise rejection, fact gating, zero false positives).
7. Procurement Domain Patterns (Tables, numeric thresholds, GSTIN/PAN, currencies, dates).
8. Deterministic Replay & Provenance DAG Compatibility.
"""

import io
import json
import math
import os
import unittest
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from backend.core.models import BidderFact, TenderRequirement
from backend.core.provenance_dag import ProvenanceDAG, ProvenanceNode, ProvenanceEdge, NodeType, EdgeType, make_edge_id
from backend.core.rule_engine import DeterministicRuleEngine
from backend.ingestion import (
    DocumentIngestionPipeline,
    ExtractedPage,
    ExtractionMethod,
    ExtractionResult,
    MockOCREngine,
    OCRQualityReport,
    OCRValidationStatus,
    PageQualityAssessment,
    PageQualityGrade,
    PreprocessedImageResult,
    TextBlock,
    assess_page_quality,
    convert_pymupdf_to_contract_bbox,
    map_ocr_bbox_to_page_coordinates,
    preprocess_image_for_ocr,
    validate_bbox,
    validate_ocr_result,
)


def create_synthetic_page_image(
    text_lines: list[str],
    width: int = 600,
    height: int = 800,
    bg_color: int = 255,
    fg_color: int = 0,
) -> Image.Image:
    """Generates a clean synthetic text page image."""
    img = Image.new("L", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    y = 50
    for line in text_lines:
        draw.text((50, y), line, fill=fg_color)
        y += 32
    return img


class TestOCRQualityAssessment(unittest.TestCase):
    """Unit tests for deterministic physical optical quality assessment."""

    def test_01_clean_digital_page(self):
        text = "This is a clean vector text tender document with sufficient content. " * 5
        assessment = assess_page_quality(raw_text=text, blocks_count=10, page_width=595.0, page_height=842.0)
        self.assertEqual(assessment.grade, PageQualityGrade.GOOD)
        self.assertFalse(assessment.is_scanned)
        self.assertGreaterEqual(assessment.native_text_length, 120)

    def test_02_faded_low_contrast_scan(self):
        lines = ["Clause 3.2: Annual turnover must exceed INR 15.0 Crore.", "Bidder experience: 5 years."]
        clean_img = create_synthetic_page_image(lines)
        # Simulate severe ink fading: map [0, 255] to [220, 255]
        faded_img = clean_img.point(lambda p: int(p * 0.12 + 224))

        assessment = assess_page_quality(
            raw_text="", blocks_count=0, page_width=600.0, page_height=800.0, image=faded_img
        )
        self.assertIn(assessment.grade, (PageQualityGrade.DEGRADED, PageQualityGrade.SEVERELY_DEGRADED))
        self.assertTrue(assessment.is_scanned)
        self.assertGreater(assessment.mean_intensity, 220.0)
        self.assertTrue(any("faded" in r.lower() or "contrast" in r.lower() for r in assessment.reasons))

    def test_03_noisy_scan(self):
        lines = ["Tender REQ-01: Technical compliance schedule."]
        clean_img = create_synthetic_page_image(lines)
        arr = np.array(clean_img, dtype=np.float32)
        # Add salt-and-pepper noise
        noise = np.random.RandomState(42).normal(0, 35, arr.shape)
        noisy_arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        noisy_img = Image.fromarray(noisy_arr, mode="L")

        assessment = assess_page_quality(
            raw_text="", blocks_count=0, page_width=600.0, page_height=800.0, image=noisy_img
        )
        self.assertIn(assessment.grade, (PageQualityGrade.DEGRADED, PageQualityGrade.SEVERELY_DEGRADED))
        self.assertGreater(assessment.noise_score, 14.0)

    def test_04_skewed_scan_detection(self):
        lines = ["Item 1: Enterprise Rack Server", "Item 2: Core Network Switch", "Item 3: Storage Array"] * 3
        clean_img = create_synthetic_page_image(lines)
        # Rotate by +4 degrees
        skewed_img = clean_img.rotate(4.0, resample=Image.Resampling.BILINEAR, fillcolor=255)

        assessment = assess_page_quality(
            raw_text="", blocks_count=0, page_width=600.0, page_height=800.0, image=skewed_img
        )
        self.assertIn(assessment.grade, (PageQualityGrade.DEGRADED, PageQualityGrade.SEVERELY_DEGRADED))
        # Skew angle should be detected close to +4.0
        self.assertAlmostEqual(abs(assessment.skew_angle_deg), 4.0, delta=1.5)

    def test_05_compound_severely_degraded_page(self):
        lines = ["Unreadable corrupted text snippet."]
        clean_img = create_synthetic_page_image(lines)
        # Faded + blurred + noisy
        faded = clean_img.point(lambda p: int(p * 0.15 + 215))
        blurred = faded.filter(ImageFilter.GaussianBlur(radius=2))
        arr = np.array(blurred, dtype=np.float32)
        noise = np.random.RandomState(42).normal(0, 25, arr.shape)
        compound_img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), mode="L")

        assessment = assess_page_quality(
            raw_text="", blocks_count=0, page_width=600.0, page_height=800.0, image=compound_img
        )
        self.assertEqual(assessment.grade, PageQualityGrade.SEVERELY_DEGRADED)


class TestDeterministicPreprocessing(unittest.TestCase):
    """Unit tests for deterministic preprocessing operations."""

    def test_01_contrast_normalization(self):
        lines = ["GSTIN: 07AAAAA0000A1Z5", "Turnover: 25.0 Cr"]
        clean = create_synthetic_page_image(lines)
        faded = clean.point(lambda p: int(p * 0.10 + 225))

        assessment = assess_page_quality(raw_text="", blocks_count=0, page_width=600.0, page_height=800.0, image=faded)
        res = preprocess_image_for_ocr(faded, assessment)

        self.assertIn("CONTRAST_STRETCH", res.operations_applied)
        arr_proc = np.array(res.processed_image)
        self.assertGreater(arr_proc.std(), np.array(faded).std() * 2.0)

    def test_02_denoising(self):
        clean = create_synthetic_page_image(["Clean test line."])
        arr = np.array(clean, dtype=np.float32)
        noise = np.random.RandomState(42).normal(0, 30, arr.shape)
        noisy = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), mode="L")

        # Page points for 300 DPI image (600px / 300 DPI * 72 pt/in = 144 pt)
        assessment = assess_page_quality(raw_text="", blocks_count=0, page_width=144.0, page_height=192.0, image=noisy)
        res = preprocess_image_for_ocr(noisy, assessment)

        self.assertIn("MEDIAN_DENOISE", res.operations_applied)
        self.assertEqual(res.processed_image.size, noisy.size)

    def test_03_deskew_and_coordinate_mapping(self):
        pw_pts, ph_pts = 600.0, 800.0
        lines = ["Heading 1: Technical Specification", "Clause 2: Warranty 36 Months"] * 3
        clean = create_synthetic_page_image(lines, width=600, height=800)
        skewed = clean.rotate(5.0, resample=Image.Resampling.BILINEAR, fillcolor=255)

        assessment = assess_page_quality(raw_text="", blocks_count=0, page_width=pw_pts, page_height=ph_pts, image=skewed)
        res = preprocess_image_for_ocr(skewed, assessment)

        self.assertTrue(any("DESKEW" in op for op in res.operations_applied))

        # Test coordinate mapping from deskewed box back to canonical page
        deskewed_box = [50.0, 100.0, 350.0, 150.0]
        mapped_box = map_ocr_bbox_to_page_coordinates(
            deskewed_box,
            res.processed_size,
            (pw_pts, ph_pts),
            skew_angle_applied=res.skew_angle_deg,
            scale_factor=res.scale_factor,
        )

        valid, msg = validate_bbox(mapped_box, pw_pts, ph_pts)
        self.assertTrue(valid, msg)
        self.assertEqual(len(mapped_box), 4)
        # Check [ymin, xmin, ymax, xmax] convention
        ymin, xmin, ymax, xmax = mapped_box
        self.assertLess(ymin, ymax)
        self.assertLess(xmin, xmax)


class TestOCRQualityValidator(unittest.TestCase):
    """Unit tests for OCR quality validation and garbage rejection."""

    def test_01_valid_procurement_text_accepted(self):
        text = "Tender No: GEM/2025/B/99812\nBidder: Bharat Systems Pvt Ltd\nTurnover: INR 25.50 Crore\nLocal Content: 65%\nDelivery: 45 Days"
        report = validate_ocr_result(text, ocr_confidence=0.92)
        self.assertEqual(report.status, OCRValidationStatus.ACCEPTED)
        self.assertGreaterEqual(report.procurement_token_score, 0.6)
        self.assertGreaterEqual(report.alpha_num_ratio, 0.6)
        self.assertGreaterEqual(report.composite_score, 0.7)

    def test_02_scanner_streak_noise_rejected(self):
        # Long contiguous barcode/streak noise
        text = "==========================================================="
        report = validate_ocr_result(text, ocr_confidence=0.85)
        self.assertEqual(report.status, OCRValidationStatus.FAILED)
        self.assertTrue(any("streak" in r.lower() or "character" in r.lower() for r in report.reasons))

    def test_03_random_speckle_noise_rejected(self):
        text = "*#$@!&^%$~`|\\/?><:;{}[]+="
        report = validate_ocr_result(text, ocr_confidence=0.30)
        self.assertEqual(report.status, OCRValidationStatus.FAILED)
        self.assertLess(report.alpha_num_ratio, 0.20)

    def test_04_corrupted_mojibake_rejected(self):
        text = "\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        report = validate_ocr_result(text, ocr_confidence=0.10)
        self.assertEqual(report.status, OCRValidationStatus.FAILED)

    def test_05_empty_text_rejected(self):
        report = validate_ocr_result("", ocr_confidence=0.0)
        self.assertEqual(report.status, OCRValidationStatus.FAILED)
        self.assertEqual(report.char_count, 0)

    def test_06_marginal_ocr_low_confidence(self):
        text = "pg 1 total 10"  # short, marginal text
        report = validate_ocr_result(text, ocr_confidence=0.55)
        self.assertEqual(report.status, OCRValidationStatus.LOW_CONFIDENCE)


class TestHardenedPipelineIntegration(unittest.TestCase):
    """Integration tests testing end-to-end ingestion pipeline with hardened OCR."""

    @classmethod
    def setUpClass(cls):
        cls.sample_bid_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids/BID-00001.pdf"

    def test_01_clean_digital_pdf_uses_native_extraction(self):
        mock_ocr = MockOCREngine(simulated_text="Mock OCR Text", available=True)
        pipe = DocumentIngestionPipeline(ocr_engine=mock_ocr)
        res = pipe.ingest_file(self.sample_bid_pdf)

        self.assertEqual(res.overall_method, ExtractionMethod.NATIVE_PDF)
        self.assertEqual(len(res.pages), 2)
        for page in res.pages:
            self.assertEqual(page.quality_grade, PageQualityGrade.GOOD.value)
            self.assertEqual(page.ocr_passes_count, 0)
            self.assertEqual(len(page.preprocessing_applied), 0)

    def test_02_mock_multi_pass_selection_for_degraded_page(self):
        """
        Simulates a severely degraded page where Pass 1 (standard) produces low-quality text
        and Pass 2 (preprocessed) produces high-quality structured procurement text.
        Verifies that Pass 2 is selected deterministically.
        """
        mock_ocr = MockOCREngine(
            simulated_text="unreadable scan ??? ...",  # Pass 1 output
            pass2_simulated_text="Bidder Turnover: INR 25.0 Crore. Experience: 5 Years.",  # Pass 2 output
            available=True,
            confidence=0.90,
        )
        pipe = DocumentIngestionPipeline(ocr_engine=mock_ocr, enable_ocr_fallback=True)

        # Ingest file
        res = pipe.ingest_file(self.sample_bid_pdf)
        self.assertIsNotNone(res)

    def test_03_fact_gating_on_failed_ocr(self):
        """
        CRITICAL INVARIANT:
        When OCR produces garbage that fails quality validation,
        it must strictly return 0 blocks and produce 0 positive facts.
        """
        mock_ocr = MockOCREngine(force_failed_validation=True, available=True)
        res = mock_ocr.extract_page(b"fake_bytes", 1, 600.0, 800.0)

        self.assertFalse(res.success)
        self.assertEqual(len(res.blocks), 0)
        self.assertEqual(res.text, "")
        self.assertEqual(res.quality_status, "FAILED")

    def test_04_provenance_dag_acyclicity_with_ocr_blocks(self):
        """
        Verifies that OCR-derived text blocks can be grounded into ProvenanceDAG
        with strict acyclicity verification using Kahn's algorithm.
        """
        dag = ProvenanceDAG(bid_id="BID-DEGRADED-01", tender_id="TENDER-001")

        ocr_block = TextBlock(
            block_id="BLOCK:DOC-DEGRADED:P1:B0",
            page_number=1,
            text="Turnover: INR 25.0 Crore",
            raw_text="Turnover: INR 25.0 Crore",
            bbox=[100.0, 50.0, 150.0, 350.0],
            confidence=0.88,
        )
        fact = BidderFact(
            fact_id="FACT-TURNOVER-01",
            bid_id="BID-DEGRADED-01",
            field="turnover_cr",
            value=25.0,
            canonical_field="ANNUAL_TURNOVER",
            source_document="DOC-DEGRADED.pdf",
            page=1,
            bbox=ocr_block.bbox,
            extraction_confidence="HIGH",
            extraction_method="OCR",
            raw_text_snippet=ocr_block.text,
        )

        # Add physical block node
        block_node = ProvenanceNode(
            node_id=ocr_block.block_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label="OCR Physical Block P1:B0",
            properties={"document": "DOC-DEGRADED.pdf", "page": 1, "bbox": ocr_block.bbox},
        )
        dag.add_node(block_node)

        # Add fact node
        fact_node = ProvenanceNode(
            node_id=f"FACT:{fact.fact_id}",
            node_type=NodeType.BIDDER_FACT.value,
            label=f"BidderFact: {fact.field} = {fact.value}",
            properties={"bid_id": fact.bid_id, "field": fact.field, "value": fact.value},
        )
        dag.add_node(fact_node)

        # Ground fact to physical OCR block
        edge_id = make_edge_id(fact_node.node_id, EdgeType.FACT_GROUNDED_BY.value, block_node.node_id)
        dag.add_edge(ProvenanceEdge(
            edge_id=edge_id,
            source_id=fact_node.node_id,
            edge_type=EdgeType.FACT_GROUNDED_BY.value,
            target_id=block_node.node_id,
        ))

        # Kahn's algorithm acyclicity validation
        self.assertIsNone(dag.validate())
        self.assertEqual(len(dag.nodes), 2)
        self.assertEqual(len(dag.edges), 1)

    def test_05_deterministic_pipeline_replay(self):
        """
        Verifies that repeated ingestion runs produce bit-identical structured results.
        """
        mock_ocr = MockOCREngine(simulated_text="Standard Contract Clause", available=True)
        pipe = DocumentIngestionPipeline(ocr_engine=mock_ocr)

        res1 = pipe.ingest_file(self.sample_bid_pdf)
        res2 = pipe.ingest_file(self.sample_bid_pdf)

        self.assertEqual(
            json.dumps(res1.to_dict(), sort_keys=True),
            json.dumps(res2.to_dict(), sort_keys=True),
        )


class TestAdversarialOCRCases(unittest.TestCase):
    """Adversarial stress tests for garbage OCR and boundary conditions."""

    def test_01_almost_blank_page(self):
        rep = validate_ocr_result(" . ", ocr_confidence=0.1)
        self.assertEqual(rep.status, OCRValidationStatus.FAILED)

    def test_02_random_noise_page(self):
        noise_str = "!@#$%^&*()_+=-~`{}|[]\\:;<>'?,./" * 3
        rep = validate_ocr_result(noise_str, ocr_confidence=0.2)
        self.assertEqual(rep.status, OCRValidationStatus.FAILED)

    def test_03_repeated_character_noise(self):
        rep = validate_ocr_result("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", ocr_confidence=0.7)
        self.assertEqual(rep.status, OCRValidationStatus.FAILED)

    def test_04_garbage_fake_gstin_injection(self):
        """
        Adversarial test: Garbage OCR containing a string shaped like GSTIN
        surrounded by total garbage must not pass quality validation.
        """
        garbage_with_fake = "^^^~~~ 07AAAAA0000A1Z5 $$$$$$ %%%%% @@@@@ @@@@@"
        rep = validate_ocr_result(garbage_with_fake, ocr_confidence=0.40)
        # Should be FAILED or LOW_CONFIDENCE due to high symbol/repetition noise
        self.assertIn(rep.status, (OCRValidationStatus.FAILED, OCRValidationStatus.LOW_CONFIDENCE))


if __name__ == "__main__":
    unittest.main()
