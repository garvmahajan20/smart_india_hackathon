# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from backend.core.models import BidderFact, TenderRequirement
from backend.core.rule_engine import DeterministicRuleEngine
from backend.extraction.evidence_grounder import EvidenceGrounder, verify_fact_support
from backend.extraction.fact_extractor import LLMBidderFactExtractor
from backend.extraction.mock_provider import MockLLMProvider
from backend.extraction.models import CandidateFact, ExtractionStatus, LLMMode
from backend.extraction.schema_validator import SchemaValidator
from backend.ingestion.models import (
    DocumentMetadata,
    DocumentType,
    ExtractedPage,
    ExtractionMethod,
    ExtractionResult,
    TextBlock,
)

class TestEvidenceGroundingHardening(unittest.TestCase):
    """
    Phase 10B.1 Focused Regression Test Suite:
    - P0.1 Multi-Block Provenance Preservation
    - P0.2 Strict Textual and Numeric Grounding
    - Anti-Hallucination Invariant Enforcement
    """

    @classmethod
    def setUpClass(cls):
        cls.validator = SchemaValidator()
        cls.rule_engine = DeterministicRuleEngine()

        cls.blocks_p1 = [
            TextBlock(
                block_id="BLK-01",
                page_number=1,
                text="Average annual turnover certified by CA: Rs. 10 Crores.",
                raw_text="",
                bbox=[100.0, 50.0, 130.0, 400.0],
            ),
            TextBlock(
                block_id="BLK-02",
                page_number=1,
                text="Bidder GSTIN: 29ABCDE1234F1Z5 | PAN: ABCDE1234F",
                raw_text="",
                bbox=[140.0, 50.0, 170.0, 400.0],
            ),
        ]

        cls.blocks_p2 = [
            TextBlock(
                block_id="BLK-03",
                page_number=2,
                text="The bidder is an authorized distributor for OEM equipment.",
                raw_text="",
                bbox=[200.0, 50.0, 230.0, 400.0],
            ),
            TextBlock(
                block_id="BLK-04",
                page_number=2,
                text="Company registered address: 123 Industrial Area, Phase II, New Delhi 110020.",
                raw_text="",
                bbox=[240.0, 50.0, 270.0, 400.0],
            ),
        ]

        cls.blocks_p3 = [
            TextBlock(
                block_id="BLK-05",
                page_number=3,
                text="Experience: The bidder possesses 36 months of past technical supply experience.",
                raw_text="",
                bbox=[300.0, 50.0, 330.0, 400.0],
            ),
            TextBlock(
                block_id="BLK-06",
                page_number=3,
                text="Warranty: 3 years comprehensive onsite warranty is provided.",
                raw_text="",
                bbox=[340.0, 50.0, 370.0, 400.0],
            ),
        ]

        cls.blocks_p4 = [
            TextBlock(
                block_id="BLK-07",
                page_number=4,
                text="Technical Specification: Server Model Dell PowerEdge R750 with Dual Intel Xeon.",
                raw_text="",
                bbox=[400.0, 50.0, 430.0, 400.0],
            ),
            TextBlock(
                block_id="BLK-08",
                page_number=4,
                text="ISO Certification: Certified compliant with ISO 9001:2015 quality management.",
                raw_text="",
                bbox=[440.0, 50.0, 470.0, 400.0],
            ),
        ]

        cls.ext_res = ExtractionResult(
            document_id="DOC-BID-HARDENING-01",
            metadata=DocumentMetadata(
                document_id="DOC-BID-HARDENING-01",
                filename="BID-SUBMISSION-01.pdf",
                file_path="BID-SUBMISSION-01.pdf",
                file_size_bytes=4096,
                sha256="aabbccddeeff11223344",
                page_count=4,
                bid_id="BID-HARDENING-01",
            ),
            pages=[
                ExtractedPage(page_number=1, width=600.0, height=800.0, text=" ".join(b.text for b in cls.blocks_p1), raw_text="", blocks=cls.blocks_p1),
                ExtractedPage(page_number=2, width=600.0, height=800.0, text=" ".join(b.text for b in cls.blocks_p2), raw_text="", blocks=cls.blocks_p2),
                ExtractedPage(page_number=3, width=600.0, height=800.0, text=" ".join(b.text for b in cls.blocks_p3), raw_text="", blocks=cls.blocks_p3),
                ExtractedPage(page_number=4, width=600.0, height=800.0, text=" ".join(b.text for b in cls.blocks_p4), raw_text="", blocks=cls.blocks_p4),
            ],
        )
        cls.grounder = EvidenceGrounder(cls.ext_res)

    # =========================================================================
    # 1. Valid numeric grounding
    # =========================================================================
    def test_01_valid_numeric_grounding(self):
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-01"],
            raw_value="Rs. 10 Crores",
            field_name="turnover_cr",
            strict=True,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.ACCEPTED)
        self.assertEqual(res.primary_page, 1)
        self.assertEqual(res.primary_bbox, [100.0, 50.0, 130.0, 400.0])

    # =========================================================================
    # 2. Valid identifier grounding
    # =========================================================================
    def test_02_valid_identifier_grounding(self):
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-02"],
            raw_value="29ABCDE1234F1Z5",
            field_name="gstin",
            strict=True,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.ACCEPTED)

    # =========================================================================
    # 3. Valid textual grounding
    # =========================================================================
    def test_03_valid_textual_grounding(self):
        # Example from prompt: Candidate "Authorized Distributor" = "YES" -> ACCEPT
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-03"],
            raw_value="YES",
            field_name="authorized_distributor",
            strict=True,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.ACCEPTED)

    # =========================================================================
    # 4. Hallucinated textual value
    # =========================================================================
    def test_04_hallucinated_textual_value(self):
        # Example from prompt: Candidate "Authorized Distributor" = "YES", Evidence "Company address: Delhi..." -> REJECT / GROUNDING_FAILED
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-04"],
            raw_value="YES",
            field_name="authorized_distributor",
            strict=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.GROUNDING_FAILED)
        self.assertIn("has no supporting keywords in cited text", res.errors[0])

    # =========================================================================
    # 5. Correct block ID but unrelated text
    # =========================================================================
    def test_05_correct_block_id_but_unrelated_text(self):
        # Correct block ID BLK-01 (Turnover block) cited for a make_model claim
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-01"],
            raw_value="Cisco Catalyst 9300 Network Switch",
            field_name="make_model",
            strict=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.GROUNDING_FAILED)

    # =========================================================================
    # 6. Wrong numeric value
    # =========================================================================
    def test_06_wrong_numeric_value(self):
        # Block BLK-01 says Rs. 10 Crores; candidate claims 25 Crore
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-01"],
            raw_value="25 Crore",
            field_name="turnover_cr",
            strict=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.GROUNDING_FAILED)
        self.assertIn("not found in source text blocks", res.errors[0])

    # =========================================================================
    # 7. Multi-block evidence
    # =========================================================================
    def test_07_multi_block_evidence(self):
        # Candidate spans BLK-03 (Page 2, Authorized distributor) and BLK-07 (Page 4, Dell PowerEdge R750)
        canned = json.dumps({"facts": [{
            "field": "oem_model_authorization",
            "raw_value": "Dell PowerEdge R750",
            "evidence_block_ids": ["BLK-03", "BLK-07"],
            "extraction_confidence": "HIGH"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK, strict_grounding=True)
        facts = extractor.extract_facts(self.ext_res, bid_id="BID-HARDENING-01")

        self.assertEqual(len(facts), 1)
        fact = facts[0]

        # 1. Backward-compatible primary attributes preserved
        self.assertEqual(fact.page, 2)
        self.assertEqual(fact.bbox, [200.0, 50.0, 230.0, 400.0])

        # 2. Multi-block structured evidence preserves ALL supporting blocks
        self.assertEqual(len(fact.evidence), 2)
        self.assertEqual(fact.evidence[0]["block_id"], "BLK-03")
        self.assertEqual(fact.evidence[0]["page"], 2)
        self.assertEqual(fact.evidence[0]["bbox"], [200.0, 50.0, 230.0, 400.0])

        self.assertEqual(fact.evidence[1]["block_id"], "BLK-07")
        self.assertEqual(fact.evidence[1]["page"], 4)
        self.assertEqual(fact.evidence[1]["bbox"], [400.0, 50.0, 430.0, 400.0])

        # 3. Metadata bboxes list present
        self.assertIn("bboxes", fact.metadata)
        self.assertEqual(len(fact.metadata["bboxes"]), 2)

        # 4. Multi-block evidence correctly propagated to VerificationResult in Step 4
        req = TenderRequirement(
            requirement_id="REQ-MODEL-01",
            tender_id="TENDER-01",
            category="TECHNICAL_SPECIFICATION",
            description="Must supply Dell PowerEdge R750",
            field="oem_model_authorization",
            operator="CONTAINS",
            expected_value="Dell PowerEdge R750",
            mandatory=True
        )
        results = self.rule_engine.verify_bid([req], facts)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "PASS")
        self.assertEqual(len(results[0].evidence), 2)
        self.assertEqual(results[0].evidence[0]["block_id"], "BLK-03")
        self.assertEqual(results[0].evidence[1]["block_id"], "BLK-07")

    # =========================================================================
    # 8. Missing block ID
    # =========================================================================
    def test_08_missing_block_id(self):
        # Empty block ID list
        res_empty = self.grounder.ground_fact(
            candidate_block_ids=[],
            raw_value="10 Crore",
            field_name="turnover_cr",
            strict=True,
        )
        self.assertFalse(res_empty.is_valid)
        self.assertEqual(res_empty.status, ExtractionStatus.GROUNDING_FAILED)

        # Unknown / non-existent block ID
        res_unknown = self.grounder.ground_fact(
            candidate_block_ids=["BLK-NON-EXISTENT-999"],
            raw_value="10 Crore",
            field_name="turnover_cr",
            strict=True,
        )
        self.assertFalse(res_unknown.is_valid)
        self.assertEqual(res_unknown.status, ExtractionStatus.GROUNDING_FAILED)

    # =========================================================================
    # 9. Duplicate block IDs
    # =========================================================================
    def test_09_duplicate_block_ids(self):
        # Candidate cites ["BLK-02", "BLK-02"]
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-02", "BLK-02"],
            raw_value="29ABCDE1234F1Z5",
            field_name="gstin",
            strict=True,
        )
        self.assertTrue(res.is_valid)
        # Exactly 1 unique evidence block preserved, no duplicates
        self.assertEqual(len(res.resolved_evidence), 1)
        self.assertEqual(res.resolved_evidence[0]["block_id"], "BLK-02")
        self.assertTrue(any("Duplicate" in w for w in res.warnings))

    # =========================================================================
    # 10. Empty extracted value
    # =========================================================================
    def test_10_empty_extracted_value(self):
        # Empty string
        res_empty_str = self.grounder.ground_fact(
            candidate_block_ids=["BLK-01"],
            raw_value="",
            field_name="turnover_cr",
            strict=True,
        )
        self.assertFalse(res_empty_str.is_valid)
        self.assertEqual(res_empty_str.status, ExtractionStatus.GROUNDING_FAILED)

        # Whitespace string
        res_whitespace = self.grounder.ground_fact(
            candidate_block_ids=["BLK-01"],
            raw_value="   ",
            field_name="turnover_cr",
            strict=True,
        )
        self.assertFalse(res_whitespace.is_valid)
        self.assertEqual(res_whitespace.status, ExtractionStatus.GROUNDING_FAILED)

        # None value under strict grounding
        res_none = self.grounder.ground_fact(
            candidate_block_ids=["BLK-01"],
            raw_value=None,
            field_name="turnover_cr",
            strict=True,
        )
        self.assertFalse(res_none.is_valid)
        self.assertEqual(res_none.status, ExtractionStatus.GROUNDING_FAILED)

    # =========================================================================
    # 11. Normalized equivalent values
    # =========================================================================
    def test_11_normalized_equivalent_values(self):
        # Example from prompt: Candidate "Experience" = "3 years", Evidence "Experience: 36 months" -> ACCEPT
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-05"],
            raw_value="3 years",
            field_name="experience",
            strict=True,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.ACCEPTED)

    # =========================================================================
    # 12. Normalized non-equivalent values
    # =========================================================================
    def test_12_normalized_non_equivalent_values(self):
        # Example from prompt: Candidate "Experience" = "5 years", Evidence "Experience: 36 months" -> REJECT
        res = self.grounder.ground_fact(
            candidate_block_ids=["BLK-05"],
            raw_value="5 years",
            field_name="experience",
            strict=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.GROUNDING_FAILED)

    # =========================================================================
    # 13. Anti-Hallucination Invariant Enforcement
    # =========================================================================
    def test_13_anti_hallucination_invariant(self):
        # Prove that ungrounded hallucinated fact cannot survive to become a BidderFact
        canned = json.dumps({"facts": [
            {
                "field": "authorized_distributor",
                "raw_value": "YES",
                "evidence_block_ids": ["BLK-04"], # Delhi address block, NOT authorization
                "extraction_confidence": "HIGH"
            },
            {
                "field": "experience_years",
                "raw_value": "10 years",
                "evidence_block_ids": ["BLK-05"], # 36 months in text, NOT 10 years
                "extraction_confidence": "HIGH"
            }
        ]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK, strict_grounding=True)
        facts = extractor.extract_facts(self.ext_res, bid_id="BID-HARDENING-01")

        # Invariant: ZERO ungrounded facts accepted into validated_facts
        self.assertEqual(len(facts), 0)

    # =========================================================================
    # 14. Contract Schema Validation with Multi-Block Evidence
    # =========================================================================
    def test_14_schema_contract_compliance_with_multi_block(self):
        fact = BidderFact(
            fact_id="FACT-001-MULTI",
            bid_id="BID-01",
            field="oem_model_authorization",
            value="Dell PowerEdge R750",
            normalized_value="DELL POWEREDGE R750",
            source_document="BID-01.pdf",
            page=2,
            bbox=[200.0, 50.0, 230.0, 400.0],
            raw_text_snippet="Dell PowerEdge R750",
            extraction_confidence="HIGH",
            evidence=[
                {
                    "block_id": "BLK-03",
                    "document": "BID-01.pdf",
                    "page": 2,
                    "bbox": [200.0, 50.0, 230.0, 400.0],
                    "snippet": "Authorized distributor",
                    "source_type": "BIDDER_SUBMISSION"
                },
                {
                    "block_id": "BLK-07",
                    "document": "BID-01.pdf",
                    "page": 4,
                    "bbox": [400.0, 50.0, 430.0, 400.0],
                    "snippet": "Dell PowerEdge R750 Server",
                    "source_type": "BIDDER_SUBMISSION"
                }
            ]
        )
        is_valid, errors = self.validator.validate_fact(fact.to_dict())
        self.assertTrue(is_valid, f"Schema validation failed: {errors}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
