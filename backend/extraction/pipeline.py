# -*- coding: utf-8 -*-
import os
from typing import Any, Dict, List, Optional, Union

from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.models import BidderFact, TenderRequirement, VerificationResult
from backend.core.rule_engine import DeterministicRuleEngine
from backend.ingestion.models import ExtractionResult
from backend.ingestion.pipeline import DocumentIngestionPipeline
from .cache import LLMCache
from .fact_extractor import LLMBidderFactExtractor
from .gemini_provider import GeminiProvider
from .mock_provider import MockLLMProvider
from .models import LLMMode
from .provider import BaseLLMProvider
from .requirement_extractor import TenderRequirementExtractor
from .schema_validator import SchemaValidator

class ExtractionPipeline:
    """
    Unified Pipeline orchestrating Step 6 ingestion, Step 7 LLM extraction,
    and feeding into Step 4 compliance and Step 5 contradiction engines.
    """

    def __init__(
        self,
        mode: Union[LLMMode, str] = LLMMode.MOCK,
        provider: Optional[BaseLLMProvider] = None,
        cache_dir: str = "data/cache/llm"
    ):
        if isinstance(mode, str):
            mode = LLMMode(mode.upper())
        self.mode = mode
        self.cache = LLMCache(cache_dir=cache_dir)
        self.validator = SchemaValidator()

        # Initialize provider
        if provider:
            self.provider = provider
        elif self.mode == LLMMode.LIVE:
            self.provider = GeminiProvider()
        else:
            self.provider = MockLLMProvider()

        self.ingestion_pipeline = DocumentIngestionPipeline()
        self.requirement_extractor = TenderRequirementExtractor(
            provider=self.provider,
            cache=self.cache,
            mode=self.mode,
            schema_validator=self.validator,
        )
        self.fact_extractor = LLMBidderFactExtractor(
            provider=self.provider,
            cache=self.cache,
            mode=self.mode,
            schema_validator=self.validator,
        )
        self.rule_engine = DeterministicRuleEngine()
        self.contradiction_engine = CrossDocumentContradictionEngine()

    def extract_tender_requirements(
        self,
        source: Union[str, ExtractionResult],
        tender_id: Optional[str] = None
    ) -> List[TenderRequirement]:
        """
        Extracts verified TenderRequirements from a PDF path or Step 6 ExtractionResult.
        """
        if isinstance(source, str):
            extraction_res = self.ingestion_pipeline.ingest_file(source, tender_id=tender_id)
        else:
            extraction_res = source

        return self.requirement_extractor.extract_requirements(extraction_res, tender_id=tender_id)

    def extract_bidder_facts(
        self,
        source: Union[str, ExtractionResult],
        bid_id: Optional[str] = None
    ) -> List[BidderFact]:
        """
        Extracts verified BidderFacts from a PDF path or Step 6 ExtractionResult.
        """
        if isinstance(source, str):
            extraction_res = self.ingestion_pipeline.ingest_file(source, bid_id=bid_id)
        else:
            extraction_res = source

        return self.fact_extractor.extract_facts(extraction_res, bid_id=bid_id)

    def verify_bid_against_tender(
        self,
        tender_source: Union[str, ExtractionResult],
        bid_source: Union[str, ExtractionResult],
        tender_id: Optional[str] = None,
        bid_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        End-to-end evaluation pipeline:
        Ingestion -> LLM Extraction -> Schema Validation -> Evidence Grounding -> Step 4 Compliance Decisions.
        """
        requirements = self.extract_tender_requirements(tender_source, tender_id=tender_id)
        facts = self.extract_bidder_facts(bid_source, bid_id=bid_id)

        # Step 4 Deterministic Rule Engine evaluation
        compliance_results = self.rule_engine.verify_bid(requirements, facts)

        return {
            "tender_id": tender_id or (requirements[0].tender_id if requirements else "UNKNOWN"),
            "bid_id": bid_id or (facts[0].bid_id if facts else "UNKNOWN"),
            "requirements_extracted": [r.to_dict() for r in requirements],
            "facts_extracted": [f.to_dict() for f in facts],
            "compliance_results": [c.to_dict() for c in compliance_results],
            "summary": {
                "total_requirements": len(requirements),
                "total_facts": len(facts),
                "pass_count": sum(1 for c in compliance_results if c.status == "PASS"),
                "fail_count": sum(1 for c in compliance_results if c.status == "FAIL"),
                "na_count": sum(1 for c in compliance_results if c.status == "N/A"),
                "review_count": sum(1 for c in compliance_results if c.status == "REVIEW"),
            }
        }
