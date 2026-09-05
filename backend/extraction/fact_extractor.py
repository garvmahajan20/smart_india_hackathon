# -*- coding: utf-8 -*-
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.core.models import BidderFact
from backend.core.normalization import (
    normalize_currency,
    normalize_duration,
    normalize_numeric,
)
from backend.ingestion.fact_extractor_interface import BaseFactExtractor
from backend.ingestion.models import ExtractionResult
from .cache import LLMCache
from .evidence_grounder import EvidenceGrounder
from .models import CandidateFact, ExtractionStatus, LLMMode
from .prompts import (
    BIDDER_FACT_SYSTEM_PROMPT,
    FACT_PROMPT_VERSION,
    format_bidder_fact_prompt,
)
from .provider import BaseLLMProvider
from .schema_validator import SchemaValidator

class LLMBidderFactExtractor(BaseFactExtractor):
    """
    Production Bidder Fact Extractor implementing BaseFactExtractor.
    Combines LLM structured candidate extraction with deterministic
    Step 6 evidence grounding and Step 4 normalization.
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        cache: Optional[LLMCache] = None,
        mode: LLMMode = LLMMode.MOCK,
        schema_validator: Optional[SchemaValidator] = None,
        strict_grounding: Optional[bool] = None,
    ):
        self.provider = provider
        self.cache = cache or LLMCache()
        self.mode = mode
        self.validator = schema_validator or SchemaValidator()
        self.strict_grounding = strict_grounding if strict_grounding is not None else (mode != LLMMode.MOCK)

    def extract_facts(
        self,
        extraction_result: ExtractionResult,
        bid_id: Optional[str] = None,
        strict: Optional[bool] = None,
    ) -> List[BidderFact]:
        effective_bid_id = bid_id or extraction_result.metadata.bid_id or "BID-UNKNOWN"
        doc_name = extraction_result.metadata.filename
        grounder = EvidenceGrounder(extraction_result)
        effective_strict = strict if strict is not None else self.strict_grounding

        prompt = format_bidder_fact_prompt(effective_bid_id, extraction_result.pages)
        cache_key = self.cache.generate_cache_key(
            provider_name=self.provider.provider_name,
            model_name=self.provider.model_name,
            prompt_version=FACT_PROMPT_VERSION,
            prompt_content=prompt,
        )

        response_text = ""
        if self.mode == LLMMode.CACHED or (self.mode == LLMMode.LIVE and self.cache.has(cache_key)):
            cached_resp = self.cache.get(cache_key)
            if cached_resp:
                response_text = cached_resp.content

        if not response_text:
            resp = self.provider.generate_structured(
                prompt=prompt,
                system_prompt=BIDDER_FACT_SYSTEM_PROMPT,
            )
            if resp.error:
                return []
            response_text = resp.content
            if self.mode == LLMMode.LIVE and not resp.is_mock:
                self.cache.set(cache_key, resp)

        candidate_facts = self._parse_candidates(response_text)
        validated_facts: List[BidderFact] = []

        for idx, cand in enumerate(candidate_facts):
            # Ground evidence in Step 6 blocks
            ground_res = grounder.ground_fact(
                candidate_block_ids=cand.evidence_block_ids,
                raw_value=cand.raw_value,
                field_name=cand.field,
                strict=effective_strict,
            )

            if not ground_res.is_valid:
                # Evidence grounding failed: reject ungrounded fact
                continue

            # Deterministic normalization of fact value
            norm_val, unit = self._normalize_fact_value(cand.raw_value, cand.field)

            fact_id = f"FACT-{effective_bid_id}-{cand.field.upper()}-{idx+1:03d}"

            fact_metadata = dict(cand.metadata or {})
            if ground_res.resolved_evidence:
                fact_metadata["evidence"] = ground_res.resolved_evidence
                fact_metadata["bboxes"] = [
                    e["bbox"] for e in ground_res.resolved_evidence if "bbox" in e and e["bbox"]
                ]

            fact_obj = BidderFact(
                fact_id=fact_id,
                bid_id=effective_bid_id,
                field=cand.field,
                value=cand.raw_value,
                normalized_value=norm_val,
                unit=unit,
                source_document=doc_name,
                page=ground_res.primary_page,
                bbox=ground_res.primary_bbox,
                raw_text_snippet=ground_res.raw_snippet[:200],
                extraction_confidence="HIGH" if ground_res.status == ExtractionStatus.ACCEPTED else "MEDIUM",
                extraction_method="LLM_STRUCTURED_EXTRACTION",
                evidence=ground_res.resolved_evidence,
                metadata=fact_metadata,
            )

            # Validate against canonical contract schema
            is_valid, _ = self.validator.validate_fact(fact_obj.to_dict())
            if is_valid:
                validated_facts.append(fact_obj)

        return validated_facts

    def _parse_candidates(self, response_text: str) -> List[CandidateFact]:
        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            data = json.loads(cleaned.strip())
            fact_list = data.get("facts", [])
            candidates = []
            for item in fact_list:
                candidates.append(CandidateFact(
                    field=item.get("field", ""),
                    raw_value=item.get("raw_value"),
                    evidence_block_ids=item.get("evidence_block_ids", []),
                    extraction_confidence=item.get("extraction_confidence", "HIGH"),
                    metadata=item.get("metadata"),
                ))
            return candidates
        except Exception:
            return []

    def _normalize_fact_value(self, val: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        if val is None:
            return None, None

        val_str = str(val).strip()

        if "turnover" in field_name.lower():
            curr_val, u = normalize_currency(val_str)
            if curr_val is not None:
                return float(curr_val), u or "INR"

        if "warranty" in field_name.lower() or "duration" in field_name.lower():
            dur_val, u = normalize_duration(val_str)
            if dur_val is not None:
                return int(dur_val), u or "MONTHS"

        if "delivery" in field_name.lower():
            dur_val, u = normalize_duration(val_str, target_unit="DAYS")
            if dur_val is not None:
                return int(dur_val), u or "DAYS"
            num_val, u = normalize_numeric(val_str)
            if num_val is not None:
                return int(num_val), u or "DAYS"

        # Standard identifiers
        if field_name in ["gstin", "pan", "udyam_number"]:
            return val_str.upper().strip(), None

        num_val, u = normalize_numeric(val_str)
        if num_val is not None:
            norm = float(num_val) if "." in str(num_val) else int(num_val)
            return norm, u

        return val_str, None
