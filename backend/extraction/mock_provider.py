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

    def _find_block_for_keyword(self, blocks: List[tuple], keywords: List[str]) -> Optional[str]:
        for b_id, b_text in blocks:
            text_lower = b_text.lower()
            if any(k in text_lower for k in keywords):
                return b_id
        return None

    def _generate_mock_tender_requirements(self, prompt: str) -> List[Dict[str, Any]]:
        reqs = []
        # Find all blocks in prompt formatted as [block_id] text
        blocks = re.findall(r"\[([^\]\n]+)\]\s*([^\n]*)", prompt)
        block_matches = [b[0] for b in blocks] if blocks else re.findall(r"\[([^\]\n]+)\]", prompt)

        # Look for turnover patterns in text
        if "turnover" in prompt.lower():
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh)", prompt, re.IGNORECASE)
            val = m.group(0) if m else "10 Crore"
            b_id = self._find_block_for_keyword(blocks, ["turnover", "crore", "cr", "lakh"]) or (block_matches[0] if block_matches else None)
            reqs.append({
                "description": f"Minimum average annual turnover of {val}",
                "category": "FINANCIAL_CAPACITY",
                "field": "turnover_cr",
                "operator": ">=",
                "expected_value": val,
                "mandatory": True,
                "evidence_block_ids": [b_id] if b_id else [],
                "source_clause": "Clause 4.1",
            })

        # Look for warranty
        if "warranty" in prompt.lower():
            m = re.search(r"(\d+)\s*(?:years?|months?)", prompt, re.IGNORECASE)
            val = m.group(0) if m else "3 years"
            b_id = self._find_block_for_keyword(blocks, ["warranty", "guarantee", "maintenance"]) or (block_matches[-1] if block_matches else None)
            reqs.append({
                "description": f"Comprehensive on-site warranty of {val}",
                "category": "TECHNICAL_SPECIFICATION",
                "field": "warranty_years",
                "operator": ">=",
                "expected_value": val,
                "mandatory": True,
                "evidence_block_ids": [b_id] if b_id else [],
                "source_clause": "Clause 8.2",
            })

        # Look for delivery
        if "delivery" in prompt.lower():
            m = re.search(r"(\d+)\s*days", prompt, re.IGNORECASE)
            val = m.group(0) if m else "60 days"
            b_id = self._find_block_for_keyword(blocks, ["delivery", "days", "schedule"]) or (block_matches[0] if block_matches else None)
            reqs.append({
                "description": f"Delivery within {val}",
                "category": "DELIVERY_LOGISTICS",
                "field": "delivery_days",
                "operator": "<=",
                "expected_value": val,
                "mandatory": True,
                "evidence_block_ids": [b_id] if b_id else [],
            })

        # Look for GST / Statutory
        if "gst" in prompt.lower() or "gstin" in prompt.lower():
            b_id = self._find_block_for_keyword(blocks, ["gst", "gstin", "tax", "registration"]) or (block_matches[0] if block_matches else None)
            reqs.append({
                "description": "Bidder must possess valid GSTIN registration",
                "category": "STATUTORY_ELIGIBILITY",
                "field": "gstin",
                "operator": "EXISTS",
                "expected_value": "Valid GSTIN",
                "mandatory": True,
                "evidence_block_ids": [b_id] if b_id else [],
                "source_clause": "Clause 2.1",
            })

        # Look for PAN
        if "pan" in prompt.lower():
            b_id = self._find_block_for_keyword(blocks, ["pan", "income tax"]) or (block_matches[0] if block_matches else None)
            reqs.append({
                "description": "Bidder must furnish Permanent Account Number (PAN)",
                "category": "STATUTORY_ELIGIBILITY",
                "field": "pan",
                "operator": "EXISTS",
                "expected_value": "Valid PAN",
                "mandatory": True,
                "evidence_block_ids": [b_id] if b_id else [],
                "source_clause": "Clause 2.2",
            })

        # Look for ISO
        if "iso" in prompt.lower():
            b_id = self._find_block_for_keyword(blocks, ["iso", "quality", "certification"]) or (block_matches[-1] if block_matches else None)
            reqs.append({
                "description": "Bidder must have valid ISO certification",
                "category": "CERTIFICATION",
                "field": "iso_cert",
                "operator": "EXISTS",
                "expected_value": "ISO 9001",
                "mandatory": True,
                "evidence_block_ids": [b_id] if b_id else [],
                "source_clause": "Clause 5.1",
            })

        # Fallback if no specific keyword matched but document has text blocks
        if not reqs and block_matches:
            b0 = block_matches[0]
            reqs.append({
                "description": "Bidder must submit valid GST registration certificate",
                "category": "STATUTORY_ELIGIBILITY",
                "field": "gstin",
                "operator": "EXISTS",
                "expected_value": "Valid GSTIN",
                "mandatory": True,
                "evidence_block_ids": [b0],
                "source_clause": "Clause 1.1",
            })
            if len(block_matches) > 1:
                b1 = block_matches[1]
                reqs.append({
                    "description": "Bidder must furnish Permanent Account Number (PAN)",
                    "category": "STATUTORY_ELIGIBILITY",
                    "field": "pan",
                    "operator": "EXISTS",
                    "expected_value": "Valid PAN",
                    "mandatory": True,
                    "evidence_block_ids": [b1],
                    "source_clause": "Clause 1.2",
                })
            if len(block_matches) > 2:
                b2 = block_matches[2]
                reqs.append({
                    "description": "Minimum financial turnover requirement of 1.0 Crore",
                    "category": "FINANCIAL_CAPACITY",
                    "field": "turnover_cr",
                    "operator": ">=",
                    "expected_value": "1.0 Crore",
                    "mandatory": True,
                    "evidence_block_ids": [b2],
                    "source_clause": "Clause 2.1",
                })

        return reqs

    def _generate_mock_bidder_facts(self, prompt: str) -> List[Dict[str, Any]]:
        facts = []
        blocks = re.findall(r"\[([^\]\n]+)\]\s*([^\n]*)", prompt)
        block_matches = [b[0] for b in blocks] if blocks else re.findall(r"\[([^\]\n]+)\]", prompt)

        # 1. Look for GSTIN in prompt & find exact block
        gst_match = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})\b", prompt)
        if gst_match:
            raw_gst = gst_match.group(1)
            b_id = self._find_block_for_keyword(blocks, [raw_gst]) or (block_matches[0] if block_matches else None)
            facts.append({
                "field": "gstin",
                "raw_value": raw_gst,
                "evidence_block_ids": [b_id] if b_id else [],
                "extraction_confidence": "HIGH",
            })

        # 2. Look for PAN in prompt & find exact block
        pan_match = re.search(r"\b([A-Z]{5}\d{4}[A-Z]{1})\b", prompt)
        if pan_match:
            raw_pan = pan_match.group(1)
            b_id = self._find_block_for_keyword(blocks, [raw_pan]) or (block_matches[0] if block_matches else None)
            facts.append({
                "field": "pan",
                "raw_value": raw_pan,
                "evidence_block_ids": [b_id] if b_id else [],
                "extraction_confidence": "HIGH",
            })

        # 3. Look for turnover
        if "turnover" in prompt.lower() or "crore" in prompt.lower() or "lakh" in prompt.lower():
            m = re.search(r"(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh)", prompt, re.IGNORECASE)
            if m:
                raw_to = m.group(0).strip()
                b_id = self._find_block_for_keyword(blocks, [raw_to, "turnover", "crore", "cr", "lakh"]) or (block_matches[0] if block_matches else None)
                facts.append({
                    "field": "turnover_cr",
                    "raw_value": raw_to,
                    "evidence_block_ids": [b_id] if b_id else [],
                    "extraction_confidence": "HIGH",
                })

        # 4. Look for warranty
        if "warranty" in prompt.lower():
            m = re.search(r"(\d+)\s*(?:years?|months?)", prompt, re.IGNORECASE)
            if m:
                raw_war = m.group(0).strip()
                b_id = self._find_block_for_keyword(blocks, [raw_war, "warranty"]) or (block_matches[0] if block_matches else None)
                facts.append({
                    "field": "warranty_years",
                    "raw_value": raw_war,
                    "evidence_block_ids": [b_id] if b_id else [],
                    "extraction_confidence": "HIGH",
                })

        # 5. Look for delivery
        if "delivery" in prompt.lower():
            m = re.search(r"(\d+)\s*days", prompt, re.IGNORECASE)
            if m:
                raw_del = m.group(0).strip()
                b_id = self._find_block_for_keyword(blocks, [raw_del, "delivery"]) or (block_matches[0] if block_matches else None)
                facts.append({
                    "field": "delivery_days",
                    "raw_value": raw_del,
                    "evidence_block_ids": [b_id] if b_id else [],
                    "extraction_confidence": "HIGH",
                })

        # 6. Look for ISO
        if "iso" in prompt.lower():
            m = re.search(r"iso\s*[-–]?\s*\d+(?::\d+)?", prompt, re.IGNORECASE)
            raw_iso = m.group(0).strip() if m else "ISO 9001"
            b_id = self._find_block_for_keyword(blocks, ["iso"]) or (block_matches[-1] if block_matches else None)
            facts.append({
                "field": "iso_cert",
                "raw_value": raw_iso,
                "evidence_block_ids": [b_id] if b_id else [],
                "extraction_confidence": "HIGH",
            })

        # Fallback if no specific facts matched but blocks exist: ground from first block text
        if not facts and blocks:
            for b_id, b_text in blocks[:2]:
                text_clean = b_text.strip()
                if len(text_clean) >= 3:
                    # Use a snippet that strictly exists in the block text
                    snippet = text_clean[:50].strip()
                    facts.append({
                        "field": "company_name",
                        "raw_value": snippet,
                        "evidence_block_ids": [b_id],
                        "extraction_confidence": "HIGH",
                    })
                    break

        return facts
