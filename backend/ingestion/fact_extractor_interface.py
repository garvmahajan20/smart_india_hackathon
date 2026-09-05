# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
import re
from typing import Any, Dict, List, Optional

from backend.core.models import BidderFact
from .evidence import build_evidence_from_block
from .models import ExtractionResult, TextBlock

class BaseFactExtractor(ABC):
    """
    Abstract interface for fact extractors.
    Provides a clean architectural boundary between document ingestion
    and semantic/parameter fact extraction (rule-based, LLM-based, or hybrid).
    """

    @abstractmethod
    def extract_facts(
        self,
        extraction_result: ExtractionResult,
        bid_id: Optional[str] = None
    ) -> List[BidderFact]:
        pass

class RuleBasedFactExtractor(BaseFactExtractor):
    """
    Deterministic rule-based fact extractor for standard GeM procurement parameters.
    Extracts key bidder parameters directly from TextBlocks and preserves
    contract-compliant [ymin, xmin, ymax, xmax] bounding boxes and text snippets.
    """

    def __init__(self):
        # Regex patterns for key procurement parameters
        self.patterns = {
            "gstin": r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b",
            "pan": r"\b[A-Z]{5}\d{4}[A-Z]{1}\b",
            "warranty_years": r"(?:warranty|guarantee)\s*(?:period)?\s*[:=-]?\s*(\d+)\s*(?:years?|yrs?|months?)",
            "turnover_cr": r"(?:turnover|revenue)\s*[:=-]?\s*(?:inr|rs\.?|₹)?\s*(\d+(?:\.\d+)?)\s*(?:crores?|cr|lakhs?|lakh)?",
            "delivery_days": r"(?:delivery|lead\s*time)\s*[:=-]?\s*(\d+)\s*days?",
            "iso_cert": r"\b(ISO\s*\d{4,5}(?::\d{4})?)\b",
        }

    def extract_facts(
        self,
        extraction_result: ExtractionResult,
        bid_id: Optional[str] = None
    ) -> List[BidderFact]:
        effective_bid_id = bid_id or extraction_result.metadata.bid_id or "BID-UNKNOWN"
        doc_name = extraction_result.metadata.filename
        facts: List[BidderFact] = []
        fact_counter = 0

        for page in extraction_result.pages:
            for block in page.blocks:
                block_text = block.text

                for field_name, pattern in self.patterns.items():
                    match = re.search(pattern, block_text, re.IGNORECASE)
                    if match:
                        fact_counter += 1
                        val: Any = match.group(1) if match.groups() else match.group(0)

                        # Type casting
                        if field_name in ["warranty_years", "delivery_days"]:
                            try:
                                val = int(val)
                            except ValueError:
                                pass
                        elif field_name == "turnover_cr":
                            try:
                                val = float(val)
                            except ValueError:
                                pass

                        extraction_method = "OCR_TEXT_EXTRACTION" if page.extraction_method.value == "OCR" else "NATIVE_PDF_PARSING"

                        facts.append(BidderFact(
                            fact_id=f"FACT-{effective_bid_id}-{field_name.upper()}-{fact_counter:03d}",
                            bid_id=effective_bid_id,
                            field=field_name,
                            value=val,
                            source_document=doc_name,
                            page=page.page_number,
                            bbox=block.bbox,
                            raw_text_snippet=block_text[:200],
                            extraction_confidence=page.extraction_confidence,
                            extraction_method=extraction_method,
                        ))

        return facts
