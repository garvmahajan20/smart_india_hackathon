# -*- coding: utf-8 -*-
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from .models import LLMProviderResponse
from .provider import BaseLLMProvider

class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic Mock LLM Provider for unit testing, CI pipelines, and offline evaluation.
    Clearly marks is_mock=True in all responses.
    """

    def __init__(
        self,
        canned_response: Optional[str] = None,
        canned_error: Optional[str] = None,
        custom_handler: Optional[Callable[[str], str]] = None
    ):
        self._canned_response = canned_response
        self._canned_error = canned_error
        self._custom_handler = custom_handler

    @property
    def provider_name(self) -> str:
        return "MockProvider"

    @property
    def model_name(self) -> str:
        model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        return f"mock-{model}"

    def is_available(self) -> bool:
        return True

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> LLMProviderResponse:
        if self._canned_error:
            return LLMProviderResponse(
                content="",
                model_name=self.model_name,
                error=self._canned_error,
                is_mock=True,
                is_cached=False,
            )

        if self._canned_response is not None:
            return LLMProviderResponse(
                content=self._canned_response,
                model_name=self.model_name,
                prompt_tokens=len(prompt) // 4,
                completion_tokens=len(self._canned_response) // 4,
                latency_ms=1.5,
                is_mock=True,
                is_cached=False,
            )

        if self._custom_handler:
            out = self._custom_handler(prompt)
            return LLMProviderResponse(
                content=out,
                model_name=self.model_name,
                prompt_tokens=len(prompt) // 4,
                completion_tokens=len(out) // 4,
                latency_ms=1.5,
                is_mock=True,
                is_cached=False,
            )

        # Dynamic mock logic based on prompt content
        # Check if bidder facts or tender requirements are requested
        if "BIDDER FACT EXTRACTION" in prompt or "bidder fact" in prompt.lower():
            facts = self._generate_mock_bidder_facts(prompt)
            return LLMProviderResponse(
                content=json.dumps({"facts": facts}),
                model_name=self.model_name,
                is_mock=True,
                latency_ms=1.0,
            )
        else:
            reqs = self._generate_mock_tender_requirements(prompt)
            return LLMProviderResponse(
                content=json.dumps({"requirements": reqs}),
                model_name=self.model_name,
                is_mock=True,
                latency_ms=1.0,
            )

    def _generate_mock_tender_requirements(self, prompt: str) -> List[Dict[str, Any]]:
        reqs = []
        # Find block ids in prompt
        block_matches = re.findall(r"\[(DOC-[^\]]+)\]", prompt)

        # Look for turnover patterns in text
        if "turnover" in prompt.lower():
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh)", prompt, re.IGNORECASE)
            val = m.group(0) if m else "10 Crore"
            bid_id_m = re.search(r"(TENDER-\d+)", prompt)
            tender_id = bid_id_m.group(1) if bid_id_m else "TENDER-0001"
            reqs.append({
                "description": f"Minimum average annual turnover of {val}",
                "category": "FINANCIAL_CAPACITY",
                "field": "turnover_cr",
                "operator": ">=",
                "expected_value": val,
                "mandatory": True,
                "evidence_block_ids": [block_matches[0]] if block_matches else [],
                "source_clause": "Clause 4.1",
            })

        # Look for warranty
        if "warranty" in prompt.lower():
            m = re.search(r"(\d+)\s*(?:years?|months?)", prompt, re.IGNORECASE)
            val = m.group(0) if m else "3 years"
            reqs.append({
                "description": f"Comprehensive on-site warranty of {val}",
                "category": "TECHNICAL_SPECIFICATION",
                "field": "warranty_years",
                "operator": ">=",
                "expected_value": val,
                "mandatory": True,
                "evidence_block_ids": [block_matches[-1]] if block_matches else [],
                "source_clause": "Clause 8.2",
            })

        # Look for delivery
        if "delivery" in prompt.lower():
            m = re.search(r"(\d+)\s*days", prompt, re.IGNORECASE)
            val = m.group(0) if m else "60 days"
            reqs.append({
                "description": f"Delivery within {val}",
                "category": "DELIVERY_LOGISTICS",
                "field": "delivery_days",
                "operator": "<=",
                "expected_value": val,
                "mandatory": True,
                "evidence_block_ids": [block_matches[0]] if block_matches else [],
            })

        return reqs

    def _generate_mock_bidder_facts(self, prompt: str) -> List[Dict[str, Any]]:
        facts = []
        block_matches = re.findall(r"\[(DOC-[^\]]+)\]", prompt)

        # Look for GSTIN in prompt
        gst_match = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})\b", prompt)
        if gst_match:
            facts.append({
                "field": "gstin",
                "raw_value": gst_match.group(1),
                "evidence_block_ids": [block_matches[0]] if block_matches else [],
                "extraction_confidence": "HIGH",
            })

        # Look for PAN in prompt
        pan_match = re.search(r"\b([A-Z]{5}\d{4}[A-Z]{1})\b", prompt)
        if pan_match:
            facts.append({
                "field": "pan",
                "raw_value": pan_match.group(1),
                "evidence_block_ids": [block_matches[0]] if block_matches else [],
                "extraction_confidence": "HIGH",
            })

        # Look for turnover
        if "turnover" in prompt.lower() or "crore" in prompt.lower() or "lakh" in prompt.lower():
            m = re.search(r"(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh)", prompt, re.IGNORECASE)
            if m:
                facts.append({
                    "field": "turnover_cr",
                    "raw_value": m.group(0).strip(),
                    "evidence_block_ids": [block_matches[0]] if block_matches else [],
                    "extraction_confidence": "HIGH",
                })

        # Look for warranty
        if "warranty" in prompt.lower():
            m = re.search(r"(\d+)\s*(?:years?|months?)", prompt, re.IGNORECASE)
            if m:
                facts.append({
                    "field": "warranty_years",
                    "raw_value": m.group(0).strip(),
                    "evidence_block_ids": [block_matches[0]] if block_matches else [],
                    "extraction_confidence": "HIGH",
                })

        # Look for delivery
        if "delivery" in prompt.lower():
            m = re.search(r"(\d+)\s*days", prompt, re.IGNORECASE)
            if m:
                facts.append({
                    "field": "delivery_days",
                    "raw_value": m.group(0).strip(),
                    "evidence_block_ids": [block_matches[0]] if block_matches else [],
                    "extraction_confidence": "HIGH",
                })

        return facts
