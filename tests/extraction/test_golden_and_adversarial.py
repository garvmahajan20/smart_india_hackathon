# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import json
import os
import unittest

sys.path.insert(0, os.path.abspath("."))

from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.models import BidderFact, TenderRequirement, VerificationResult
from backend.core.rule_engine import DeterministicRuleEngine
from backend.extraction.cache import LLMCache
from backend.extraction.evidence_grounder import EvidenceGrounder
from backend.extraction.fact_extractor import LLMBidderFactExtractor
from backend.extraction.gemini_provider import GeminiProvider
from backend.extraction.mock_provider import MockLLMProvider
from backend.extraction.models import (
    CandidateFact,
    CandidateRequirement,
    ExtractionStatus,
    LLMMode,
    LLMProviderResponse,
)
from backend.extraction.pipeline import ExtractionPipeline
from backend.extraction.requirement_extractor import TenderRequirementExtractor
from backend.extraction.schema_validator import SchemaValidator
from backend.ingestion.models import (
    DocumentMetadata,
    DocumentType,
    ExtractedPage,
    ExtractionMethod,
    ExtractionResult,
    TextBlock,
)

class TestStep7GoldenAndAdversarial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = SchemaValidator()
        cls.rule_engine = DeterministicRuleEngine()
        cls.contra_engine = CrossDocumentContradictionEngine()

        # Build a synthetic ExtractionResult fixture with known blocks for test grounding
        cls.sample_blocks_p1 = [
            TextBlock(block_id="BLK-P1-001", page_number=1, text="TENDER FOR PROCUREMENT OF IT EQUIPMENT", raw_text="", bbox=[50.0, 50.0, 80.0, 500.0]),
            TextBlock(block_id="BLK-P1-002", page_number=1, text="Clause 4.1: The bidder must have an average annual turnover of at least Rs. 10 Crores during last 3 years.", raw_text="", bbox=[100.0, 50.0, 140.0, 550.0]),
            TextBlock(block_id="BLK-P1-003", page_number=1, text="Clause 5.2: Delivery shall be completed within 60 days of order.", raw_text="", bbox=[150.0, 50.0, 180.0, 450.0]),
            TextBlock(block_id="BLK-P1-004", page_number=1, text="Clause 6.1: Bidder must possess valid ISO 9001:2015 certification.", raw_text="", bbox=[200.0, 50.0, 230.0, 480.0]),
            TextBlock(block_id="BLK-P1-005", page_number=1, text="Clause 7.1: Bid validity date: Bid must be valid on 2026-12-31.", raw_text="", bbox=[250.0, 50.0, 280.0, 460.0]),
        ]
        cls.sample_blocks_p2 = [
            TextBlock(block_id="BLK-P2-001", page_number=2, text="Company: Bharat Devices Pvt Ltd", raw_text="", bbox=[50.0, 50.0, 75.0, 300.0]),
            TextBlock(block_id="BLK-P2-002", page_number=2, text="GSTIN: 29SYNTH0000003F1Z | PAN: SYNTH0003F", raw_text="", bbox=[80.0, 50.0, 110.0, 400.0]),
            TextBlock(block_id="BLK-P2-003", page_number=2, text="We confirm comprehensive on-site warranty of 36 months.", raw_text="", bbox=[120.0, 50.0, 150.0, 450.0]),
            TextBlock(block_id="BLK-P2-004", page_number=2, text="Audited average annual turnover: Rs. 12.50 Crores.", raw_text="", bbox=[160.0, 50.0, 190.0, 420.0]),
        ]

        cls.tender_ext_res = ExtractionResult(
            document_id="DOC-TENDER-GOLDEN",
            metadata=DocumentMetadata(
                document_id="DOC-TENDER-GOLDEN",
                filename="TENDER-GOLDEN.pdf",
                file_path="TENDER-GOLDEN.pdf",
                file_size_bytes=1024,
                sha256="abc123hash",
                page_count=1,
                tender_id="TENDER-GOLDEN",
            ),
            pages=[ExtractedPage(page_number=1, width=600.0, height=800.0, text="", raw_text="", blocks=cls.sample_blocks_p1)],
        )

        cls.bid_ext_res = ExtractionResult(
            document_id="DOC-BID-GOLDEN",
            metadata=DocumentMetadata(
                document_id="DOC-BID-GOLDEN",
                filename="BID-GOLDEN.pdf",
                file_path="BID-GOLDEN.pdf",
                file_size_bytes=2048,
                sha256="def456hash",
                page_count=2,
                bid_id="BID-GOLDEN",
            ),
            pages=[
                ExtractedPage(page_number=1, width=600.0, height=800.0, text="", raw_text="", blocks=[]),
                ExtractedPage(page_number=2, width=600.0, height=800.0, text="", raw_text="", blocks=cls.sample_blocks_p2),
            ],
        )

    # =========================================================================
    # PART 1: 12 GOLDEN TEST CASES (Section 29)
    # =========================================================================

    # 1. Turnover requirement
    def test_golden_01_turnover_requirement(self):
        canned = json.dumps({"requirements": [{
            "description": "Minimum average annual turnover of Rs. 10 Crores",
            "category": "FINANCIAL_CAPACITY",
            "field": "turnover_cr",
            "operator": ">=",
            "expected_value": "Rs. 10 Crores",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-002"],
            "source_clause": "Clause 4.1"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res, tender_id="TENDER-GOLDEN")
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].field, "turnover_cr")
        self.assertEqual(reqs[0].normalized_expected_value, 100000000.0)
        self.assertEqual(reqs[0].evidence[0]["bbox"], [100.0, 50.0, 140.0, 550.0])

    # 2. Delivery period requirement
    def test_golden_02_delivery_period_requirement(self):
        canned = json.dumps({"requirements": [{
            "description": "Delivery shall be completed within 60 days",
            "category": "DELIVERY_LOGISTICS",
            "field": "delivery_days",
            "operator": "<=",
            "expected_value": "60 days",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-003"]
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].field, "delivery_days")
        self.assertEqual(reqs[0].operator, "<=")
        self.assertEqual(reqs[0].normalized_expected_value, 60)

    # 3. Certificate requirement
    def test_golden_03_certificate_requirement(self):
        canned = json.dumps({"requirements": [{
            "description": "Valid ISO 9001:2015 certification",
            "category": "CERTIFICATION",
            "field": "iso_cert",
            "operator": "EXISTS",
            "expected_value": "ISO 9001:2015",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-004"]
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].category, "CERTIFICATION")
        self.assertEqual(reqs[0].operator, "EXISTS")

    # 4. Date validity requirement
    def test_golden_04_date_validity_requirement(self):
        canned = json.dumps({"requirements": [{
            "description": "Bid must be valid on 2026-12-31",
            "category": "COMMERCIAL_TERMS",
            "field": "validity_date",
            "operator": "VALID_ON",
            "expected_value": "2026-12-31",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-005"]
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].operator, "VALID_ON")

    # 5. Identity fact
    def test_golden_05_identity_fact(self):
        canned = json.dumps({"facts": [{
            "field": "company_name",
            "raw_value": "Bharat Devices Pvt Ltd",
            "evidence_block_ids": ["BLK-P2-001"],
            "extraction_confidence": "HIGH"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK)
        facts = extractor.extract_facts(self.bid_ext_res)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].field, "company_name")
        self.assertEqual(facts[0].value, "Bharat Devices Pvt Ltd")
        self.assertEqual(facts[0].page, 2)

    # 6. GSTIN fact
    def test_golden_06_gstin_fact(self):
        canned = json.dumps({"facts": [{
            "field": "gstin",
            "raw_value": "29SYNTH0000003F1Z",
            "evidence_block_ids": ["BLK-P2-002"],
            "extraction_confidence": "HIGH"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK)
        facts = extractor.extract_facts(self.bid_ext_res)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].normalized_value, "29SYNTH0000003F1Z")

    # 7. PAN fact
    def test_golden_07_pan_fact(self):
        canned = json.dumps({"facts": [{
            "field": "pan",
            "raw_value": "SYNTH0003F",
            "evidence_block_ids": ["BLK-P2-002"],
            "extraction_confidence": "HIGH"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK)
        facts = extractor.extract_facts(self.bid_ext_res)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].normalized_value, "SYNTH0003F")

    # 8. Warranty fact
    def test_golden_08_warranty_fact(self):
        canned = json.dumps({"facts": [{
            "field": "warranty_years",
            "raw_value": "36 months",
            "evidence_block_ids": ["BLK-P2-003"],
            "extraction_confidence": "HIGH"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK)
        facts = extractor.extract_facts(self.bid_ext_res)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].normalized_value, 36)
        self.assertEqual(facts[0].unit, "MONTHS")

    # 9. Missing fact (tender asks for ISO 14001, bid did not submit it)
    def test_golden_09_missing_fact(self):
        req = TenderRequirement(
            requirement_id="REQ-ISO14001",
            tender_id="TENDER-GOLDEN",
            category="CERTIFICATION",
            description="Must possess ISO 14001 certification",
            field="iso_14001",
            operator="EXISTS",
            expected_value=True,
            mandatory=True
        )
        # Bidder facts contain no iso_14001
        res = self.rule_engine.verify_bid([req], [])
        self.assertEqual(res[0].status, "MISSING")
        self.assertIn("missing", res[0].reason.lower())

    # 10. Ambiguous statement flagged for review
    def test_golden_10_ambiguous_statement_review(self):
        # Claiming value whose digits do not appear in referenced block
        grounder = EvidenceGrounder(self.tender_ext_res)
        res = grounder.ground_requirement(
            candidate_block_ids=["BLK-P1-002"],
            expected_value="500 Crores", # P1-002 actually says 10 Crores!
            description="Claimed 500 Crores"
        )
        self.assertEqual(res.status, ExtractionStatus.REVIEW_REQUIRED)
        self.assertGreater(len(res.warnings), 0)

    # 11. Multi-page requirement
    def test_golden_11_multi_page_requirement(self):
        # Combined tender result having 2 pages
        multi_tender = ExtractionResult(
            document_id="DOC-MULTI",
            metadata=self.tender_ext_res.metadata,
            pages=[
                self.tender_ext_res.pages[0],
                self.bid_ext_res.pages[1], # Page 2
            ]
        )
        grounder = EvidenceGrounder(multi_tender)
        res = grounder.ground_requirement(candidate_block_ids=["BLK-P1-002", "BLK-P2-003"])
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.resolved_evidence), 2)
        self.assertEqual(res.resolved_evidence[0]["page"], 1)
        self.assertEqual(res.resolved_evidence[1]["page"], 2)

    # 12. Contradiction across two documents
    def test_golden_12_contradiction_across_two_documents(self):
        finding = self.contra_engine.evaluate_pair(
            contradiction_id="CONTRA-GOLDEN-01",
            bid_id="BID-GOLDEN",
            field_name="gstin",
            value_a="29SYNTH0000003F1Z",
            value_b="29SYNTH0000103F1Z",
            document_a="tech_bid.pdf",
            page_a=1,
            bbox_a=[50.0, 50.0, 75.0, 200.0],
            snippet_a="GSTIN: 29SYNTH0000003F1Z",
            document_b="financial_bid.pdf",
            page_b=2,
            bbox_b=[100.0, 50.0, 125.0, 200.0],
            snippet_b="GSTIN: 29SYNTH0000103F1Z",
        )
        self.assertEqual(finding.status, "CONTRADICTION")
        self.assertEqual(finding.severity, "HIGH")

    # =========================================================================
    # PART 2: 14 ADVERSARIAL / NEGATIVE TEST CASES (Section 30)
    # =========================================================================

    # 1. Missing value
    def test_adversarial_01_missing_value(self):
        canned = json.dumps({"facts": [{"field": "turnover_cr", "raw_value": None, "evidence_block_ids": ["BLK-P2-004"]}]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK)
        facts = extractor.extract_facts(self.bid_ext_res)
        self.assertEqual(len(facts), 1)
        self.assertIsNone(facts[0].value)

    # 2. Conflicting values in same chunk
    def test_adversarial_02_conflicting_values_in_same_chunk(self):
        # A single document declaring 2 different turnover values on page 2
        f1 = BidderFact(fact_id="F1", bid_id="BID-01", field="turnover_cr", value="10 Crore", source_document="doc.pdf", page=2, extraction_confidence="HIGH")
        f2 = BidderFact(fact_id="F2", bid_id="BID-01", field="turnover_cr", value="15 Crore", source_document="doc.pdf", page=2, extraction_confidence="HIGH")
        finding = self.contra_engine.evaluate_pair("C1", "BID-01", "turnover_cr", f1.value, f2.value, "doc.pdf", 2, None, "", "doc.pdf", 2, None, "")
        self.assertEqual(finding.status, "CONTRADICTION")

    # 3. Irrelevant number ignored
    def test_adversarial_03_irrelevant_number(self):
        canned = json.dumps({"requirements": []}) # LLM safely ignores room number or phone number
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 0)

    # 4. Multiple dates in text
    def test_adversarial_04_multiple_dates(self):
        canned = json.dumps({"requirements": [{
            "description": "Bid must be valid on 2026-12-31",
            "category": "COMMERCIAL_TERMS",
            "field": "validity_date",
            "operator": "VALID_ON",
            "expected_value": "2026-12-31",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-005"]
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(reqs[0].expected_value, "2026-12-31")

    # 5. Multiple currencies normalized to INR
    def test_adversarial_05_multiple_currencies(self):
        canned = json.dumps({"facts": [
            {"field": "turnover_cr", "raw_value": "Rs. 10 Lakh", "evidence_block_ids": ["BLK-P2-004"]},
            {"field": "turnover_cr", "raw_value": "INR 1000000", "evidence_block_ids": ["BLK-P2-004"]},
        ]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = LLMBidderFactExtractor(provider=prov, mode=LLMMode.MOCK)
        facts = extractor.extract_facts(self.bid_ext_res)
        self.assertEqual(facts[0].normalized_value, 1000000.0)
        self.assertEqual(facts[1].normalized_value, 1000000.0)

    # 6. Ambiguous legal name
    def test_adversarial_06_ambiguous_legal_name(self):
        finding = self.contra_engine.evaluate_pair(
            "C-NAME", "BID-01", "company_name",
            "ABC INFRASTRUCTURE PRIVATE LIMITED", "ABC INFRASTRUCTURE SERVICES PRIVATE LIMITED",
            "doc1.pdf", 1, None, "", "doc2.pdf", 1, None, ""
        )
        self.assertTrue(finding.requires_human_review)

    # 7. Unsupported operator rejected
    def test_adversarial_07_unsupported_operator(self):
        canned = json.dumps({"requirements": [{
            "description": "Turnover approx 10 Cr",
            "category": "FINANCIAL_CAPACITY",
            "field": "turnover_cr",
            "operator": "APPROXIMATELY", # Invalid operator
            "expected_value": "10 Cr",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-002"]
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        # Unsupported operator must NOT be silently accepted
        self.assertEqual(len(reqs), 0)

    # 8. Missing evidence block ID rejected
    def test_adversarial_08_missing_evidence_block(self):
        canned = json.dumps({"requirements": [{
            "description": "Ghost requirement",
            "category": "FINANCIAL_CAPACITY",
            "field": "turnover_cr",
            "operator": ">=",
            "expected_value": "10 Cr",
            "mandatory": True,
            "evidence_block_ids": ["NON_EXISTENT_BLOCK_999"]
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 0)

    # 9. Invalid page reference
    def test_adversarial_09_invalid_page_reference(self):
        grounder = EvidenceGrounder(self.tender_ext_res)
        res = grounder.ground_requirement(candidate_block_ids=["BLK-P99-999"])
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ExtractionStatus.GROUNDING_FAILED)

    # 10. Malformed LLM JSON handled gracefully
    def test_adversarial_10_malformed_llm_json(self):
        malformed = "NOT A JSON OBJECT AT ALL { requirements: [broken"
        prov = MockLLMProvider(canned_response=malformed)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 0)

    # 11. Extra unexpected JSON fields handled safely
    def test_adversarial_11_extra_unexpected_json_fields(self):
        canned = json.dumps({"requirements": [{
            "description": "Valid requirement with extra AI hallucinated keys",
            "category": "FINANCIAL_CAPACITY",
            "field": "turnover_cr",
            "operator": ">=",
            "expected_value": "10 Crore",
            "mandatory": True,
            "evidence_block_ids": ["BLK-P1-002"],
            "hallucinated_compliance_score": 0.999,
            "ai_verdict": "PASS"
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 1)
        req_dict = reqs[0].to_dict()
        # Schema validation enforces strict contract
        is_valid, errors = self.validator.validate_requirement(req_dict)
        self.assertTrue(is_valid, errors)
        self.assertNotIn("hallucinated_compliance_score", req_dict)

    # 12. Empty LLM response
    def test_adversarial_12_empty_llm_response(self):
        prov = MockLLMProvider(canned_response="")
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 0)

    # 13. Provider timeout / error
    def test_adversarial_13_provider_error(self):
        prov = MockLLMProvider(canned_error="Gateway Timeout 504")
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.tender_ext_res)
        self.assertEqual(len(reqs), 0)

    # 14. Unavailable API credentials fails safely
    def test_adversarial_14_unavailable_api_credentials(self):
        gemini_no_key = GeminiProvider(api_key="")
        self.assertFalse(gemini_no_key.is_available())
        resp = gemini_no_key.generate_structured("Extract something")
        self.assertIn("not configured", resp.error)
        self.assertEqual(resp.content, "")

    # 15. Model configuration resolves to gemini-3.8-flash and supports explicit override
    def test_adversarial_15_model_configuration_and_override(self):
        default_prov = GeminiProvider(api_key="mock_key")
        self.assertEqual(default_prov.model_name, "gemini-3.8-flash")
        self.assertEqual(default_prov.fallback_model, "gemini-3.7-flash")

        custom_prov = GeminiProvider(api_key="mock_key", model_name="custom-flash", fallback_model="custom-fallback")
        self.assertEqual(custom_prov.model_name, "custom-flash")
        self.assertEqual(custom_prov.fallback_model, "custom-fallback")

    # 16. Bounded single fallback operates correctly
    def test_adversarial_16_bounded_fallback(self):
        prov = GeminiProvider(api_key="mock_key", model_name="failing-model", fallback_model="working-fallback")
        
        # Mock _execute_request to simulate 404 on primary, success on fallback
        def mock_exec(model, payload):
            if model == "failing-model":
                return LLMProviderResponse(content="", model_name=model, error="Gemini API error (404): NOT_FOUND")
            elif model == "working-fallback":
                return LLMProviderResponse(content="{\"status\": \"FALLBACK_OK\"}", model_name=model)
            return LLMProviderResponse(content="", model_name=model, error="Unknown model")

        prov._execute_request = mock_exec
        resp = prov.generate_structured("test")
        self.assertEqual(resp.model_name, "working-fallback")
        self.assertEqual(resp.content, "{\"status\": \"FALLBACK_OK\"}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
