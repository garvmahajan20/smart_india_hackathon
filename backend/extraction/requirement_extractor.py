# -*- coding: utf-8 -*-
import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.models import TenderRequirement
from backend.core.normalization import (
    normalize_currency,
    normalize_duration,
    normalize_numeric,
)
from backend.ingestion.models import ExtractionResult
from .cache import LLMCache
from .evidence_grounder import EvidenceGrounder
from .models import CandidateRequirement, ExtractionStatus, LLMMode
from .prompts import (
    REQUIREMENT_PROMPT_VERSION,
    TENDER_REQUIREMENT_SYSTEM_PROMPT,
    format_tender_requirement_prompt,
    TENDER_EXHAUSTIVE_CONDITION_SYSTEM_PROMPT,
    TENDER_BIDDER_OBLIGATION_SYSTEM_PROMPT,
    format_page_condition_prompt,
    format_tender_bidder_obligation_prompt,
)
from .provider import BaseLLMProvider
from .schema_validator import SchemaValidator

ALLOWED_OPERATORS: Set[str] = {
    ">=", "<=", ">", "<", "==", "!=",
    "IN", "NOT_IN", "CONTAINS", "MATCHES",
    "EXISTS", "VALID_ON", "BEFORE", "AFTER", "BETWEEN"
}

ALLOWED_CATEGORIES: Set[str] = {
    "FINANCIAL_CAPACITY", "TECHNICAL_SPECIFICATION", "EXPERIENCE_PAST_PERFORMANCE",
    "CERTIFICATION", "STATUTORY_ELIGIBILITY", "LEGAL_UNDERTAKING",
    "COMMERCIAL_TERMS", "DELIVERY_LOGISTICS", "MSE_MII_PREFERENCE", "OTHER"
}

class TenderRequirementExtractor:
    """
    Orchestrates Tender Requirement Extraction with LLM parsing,
    strict schema validation, evidence grounding, and deterministic normalization.
    Supports both two-pass (page-aware condition discovery + document-level bidder obligation)
    and single-pass extraction for backward compatibility.
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        cache: Optional[LLMCache] = None,
        mode: LLMMode = LLMMode.MOCK,
        schema_validator: Optional[SchemaValidator] = None,
        two_pass: bool = True,
    ):
        self.provider = provider
        self.cache = cache or LLMCache()
        self.mode = mode
        self.validator = schema_validator or SchemaValidator()
        self.two_pass = two_pass

    def extract_requirements(
        self,
        extraction_result: ExtractionResult,
        tender_id: Optional[str] = None
    ) -> List[TenderRequirement]:
        effective_tender_id = tender_id or extraction_result.metadata.tender_id or "TENDER-UNKNOWN"
        grounder = EvidenceGrounder(extraction_result)

        # Check if provider has a canned response or if two-pass is disabled
        is_canned = hasattr(self.provider, "_canned_response") and self.provider._canned_response is not None
        if is_canned or not self.two_pass:
            candidate_reqs = self._extract_single_pass(effective_tender_id, extraction_result)
        else:
            candidate_reqs = self._extract_two_pass(effective_tender_id, extraction_result)

        # Decompose compound clauses
        decomposed_candidates = self._decompose_compound_candidates(candidate_reqs)

        # Merge and deduplicate
        unique_candidates = self._merge_and_deduplicate_candidates(decomposed_candidates)

        validated_requirements: List[TenderRequirement] = []
        seen_dedup_keys: Set[str] = set()

        for idx, cand in enumerate(unique_candidates):
            # Validate operator
            op = (cand.operator or "").strip()
            if op not in ALLOWED_OPERATORS:
                continue

            # Validate category
            cat = (cand.category or "").strip()
            if cat not in ALLOWED_CATEGORIES:
                cat = "OTHER"

            # Ground evidence
            ground_res = grounder.ground_requirement(
                candidate_block_ids=cand.evidence_block_ids,
                expected_value=cand.expected_value,
                description=cand.description,
            )

            if not ground_res.is_valid:
                # Evidence grounding failed: reject extraction
                continue

            # Deterministic normalization of expected_value
            norm_val, unit = self._normalize_expected_value(cand.expected_value, cand.field)

            req_id = f"REQ-{effective_tender_id}-{idx+1:03d}"

            # Conservative deduplication key
            dedup_key = f"{effective_tender_id}:{cand.field}:{op}:{str(norm_val)}"
            if dedup_key in seen_dedup_keys:
                continue
            seen_dedup_keys.add(dedup_key)

            # Preserve requirement_type in applicability (schema compliant)
            appl = dict(cand.applicability) if cand.applicability else {}
            if cand.requirement_type:
                appl["requirement_type"] = cand.requirement_type

            req_obj = TenderRequirement(
                requirement_id=req_id,
                tender_id=effective_tender_id,
                category=cat,
                description=cand.description,
                field=cand.field or "unspecified_parameter",
                operator=op,
                expected_value=cand.expected_value,
                normalized_expected_value=norm_val,
                unit=unit,
                mandatory=cand.mandatory,
                source_type="UNSPECIFIED",
                source_clause=cand.source_clause,
                source_page=ground_res.primary_page,
                source_priority=0,
                applicability=appl if appl else None,
                evidence=ground_res.resolved_evidence,
                extraction_confidence="HIGH" if ground_res.status == ExtractionStatus.ACCEPTED else "MEDIUM",
            )

            # Validate against canonical contract schema
            is_valid, _ = self.validator.validate_requirement(req_obj.to_dict())
            if is_valid:
                validated_requirements.append(req_obj)

        return validated_requirements

    def _extract_single_pass(
        self,
        effective_tender_id: str,
        extraction_result: ExtractionResult
    ) -> List[CandidateRequirement]:
        prompt = format_tender_requirement_prompt(effective_tender_id, extraction_result.pages)
        cache_key = self.cache.generate_cache_key(
            provider_name=self.provider.provider_name,
            model_name=self.provider.model_name,
            prompt_version=REQUIREMENT_PROMPT_VERSION,
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
                system_prompt=TENDER_REQUIREMENT_SYSTEM_PROMPT,
            )
            if resp.error:
                return []
            response_text = resp.content
            if self.mode == LLMMode.LIVE and not resp.is_mock:
                self.cache.set(cache_key, resp)

        return self._parse_candidates(response_text)

    def _extract_two_pass(
        self,
        effective_tender_id: str,
        extraction_result: ExtractionResult
    ) -> List[CandidateRequirement]:
        raw_candidates: List[CandidateRequirement] = []

        # PASS 1: Page-aware exhaustive procurement condition discovery
        for page in extraction_result.pages:
            p1_prompt = format_page_condition_prompt(effective_tender_id, page)
            p1_cache_key = self.cache.generate_cache_key(
                provider_name=self.provider.provider_name,
                model_name=self.provider.model_name,
                prompt_version=f"{REQUIREMENT_PROMPT_VERSION}-pass1-p{page.page_number}",
                prompt_content=p1_prompt,
            )
            p1_text = ""
            if self.mode == LLMMode.CACHED or (self.mode == LLMMode.LIVE and self.cache.has(p1_cache_key)):
                cached_resp = self.cache.get(p1_cache_key)
                if cached_resp:
                    p1_text = cached_resp.content

            if not p1_text:
                resp = self.provider.generate_structured(
                    prompt=p1_prompt,
                    system_prompt=TENDER_EXHAUSTIVE_CONDITION_SYSTEM_PROMPT,
                )
                if resp.error:
                    print(f"Extraction warning on page {page.page_number}: {resp.error}")
                if not resp.error and resp.content:
                    p1_text = resp.content
                    if self.mode == LLMMode.LIVE and not resp.is_mock:
                        self.cache.set(p1_cache_key, resp)
                if self.mode == LLMMode.LIVE and not getattr(resp, "is_mock", False):
                    time.sleep(1.0)

            if p1_text:
                page_candidates = self._parse_candidates(p1_text, default_source_pass="PASS_1_EXHAUSTIVE")
                raw_candidates.extend(page_candidates)

        # PASS 2: Targeted bidder-obligation discovery across all pages
        p2_prompt = format_tender_bidder_obligation_prompt(effective_tender_id, extraction_result.pages)
        p2_cache_key = self.cache.generate_cache_key(
            provider_name=self.provider.provider_name,
            model_name=self.provider.model_name,
            prompt_version=f"{REQUIREMENT_PROMPT_VERSION}-pass2",
            prompt_content=p2_prompt,
        )
        p2_text = ""
        if self.mode == LLMMode.CACHED or (self.mode == LLMMode.LIVE and self.cache.has(p2_cache_key)):
            cached_resp = self.cache.get(p2_cache_key)
            if cached_resp:
                p2_text = cached_resp.content

        if not p2_text:
            resp_p2 = self.provider.generate_structured(
                prompt=p2_prompt,
                system_prompt=TENDER_BIDDER_OBLIGATION_SYSTEM_PROMPT,
            )
            if resp_p2.error:
                print(f"Extraction warning on pass 2: {resp_p2.error}")
            if not resp_p2.error and resp_p2.content:
                p2_text = resp_p2.content
                if self.mode == LLMMode.LIVE and not resp_p2.is_mock:
                    self.cache.set(p2_cache_key, resp_p2)

        if p2_text:
            pass2_candidates = self._parse_candidates(p2_text, default_source_pass="PASS_2_BIDDER_OBLIGATION")
            raw_candidates.extend(pass2_candidates)

        return raw_candidates

    def _decompose_compound_candidates(self, candidates: List[CandidateRequirement]) -> List[CandidateRequirement]:
        decomposed: List[CandidateRequirement] = []

        for c in candidates:
            desc = c.description or ""
            desc_lower = desc.lower()
            val_str = str(c.expected_value or "")
            val_lower = val_str.lower()
            fld_lower = str(c.field or "").lower()

            # Check for footnote / asterisk exemption combined with BoQ / document requirement
            if ("exemption" in desc_lower and ("boq" in desc_lower or "compliance" in desc_lower or "document required" in desc_lower) and ("*" in desc or "seeking exemption" in desc_lower)):
                decomposed.append(CandidateRequirement(
                    description="Compliance of BoQ specification and supporting document required from seller",
                    category="TECHNICAL_SPECIFICATION",
                    field="boq_compliance_document",
                    operator="EXISTS",
                    expected_value="Compliance of BoQ specification and supporting document",
                    mandatory=True,
                    evidence_block_ids=c.evidence_block_ids,
                    source_clause=c.source_clause,
                    applicability=c.applicability,
                    extraction_confidence=c.extraction_confidence,
                    requirement_type="BIDDER_COMPLIANCE",
                    source_pass=c.source_pass,
                ))
                decomposed.append(CandidateRequirement(
                    description="Supporting documents to prove eligibility for exemption from Experience / Turnover Criteria must be uploaded for evaluation by buyer",
                    category="STATUTORY_ELIGIBILITY",
                    field="exemption_supporting_documents",
                    operator="EXISTS",
                    expected_value="Supporting documents to prove eligibility for exemption must be uploaded",
                    mandatory=True,
                    evidence_block_ids=c.evidence_block_ids,
                    source_clause="Footnote / Proviso",
                    applicability=c.applicability,
                    extraction_confidence=c.extraction_confidence,
                    requirement_type="BIDDER_COMPLIANCE",
                    source_pass=c.source_pass,
                ))
            elif ("land border" in desc_lower and "undertaking" in desc_lower and "competent authority" in desc_lower and "registration" in desc_lower):
                decomposed.append(CandidateRequirement(
                    description="Any bidder from a country sharing a land border with India will be eligible to bid only if registered with the Competent Authority",
                    category="STATUTORY_ELIGIBILITY",
                    field="land_border_registration",
                    operator="==",
                    expected_value="Registered with Competent Authority",
                    mandatory=True,
                    evidence_block_ids=c.evidence_block_ids,
                    source_clause=c.source_clause,
                    applicability=c.applicability,
                    extraction_confidence=c.extraction_confidence,
                    requirement_type="BIDDER_COMPLIANCE",
                    source_pass=c.source_pass,
                ))
                decomposed.append(CandidateRequirement(
                    description="Bidder must submit an affirmative undertaking certifying compliance with Land Border restrictions under GeM GTC Clause 26; false declaration constitutes breach",
                    category="LEGAL_UNDERTAKING",
                    field="land_border_compliance_undertaking",
                    operator="EXISTS",
                    expected_value="Affirmative undertaking certifying compliance with Clause 26",
                    mandatory=True,
                    evidence_block_ids=c.evidence_block_ids,
                    source_clause=c.source_clause,
                    applicability=c.applicability,
                    extraction_confidence=c.extraction_confidence,
                    requirement_type="BIDDER_COMPLIANCE",
                    source_pass=c.source_pass,
                ))
            elif "documents_required_from_seller" in fld_lower or "document_required_from_seller" in fld_lower or "documents required from seller" in desc_lower:
                decomposed.append(c)
                combined_text = (desc + " " + val_str).lower()
                if "oem annual turnover" in combined_text:
                    decomposed.append(CandidateRequirement(
                        description="OEM Annual Turnover documentary proof required from seller",
                        category="FINANCIAL_CAPACITY",
                        field="oem_annual_turnover_document",
                        operator="EXISTS",
                        expected_value="OEM Annual Turnover document",
                        mandatory=True,
                        evidence_block_ids=c.evidence_block_ids,
                        source_clause=c.source_clause or "Document required from seller",
                        applicability=c.applicability,
                        extraction_confidence=c.extraction_confidence,
                        requirement_type="BIDDER_COMPLIANCE",
                        source_pass=c.source_pass,
                    ))
                if "oem authorization" in combined_text:
                    decomposed.append(CandidateRequirement(
                        description="OEM Authorization Certificate required from seller",
                        category="CERTIFICATION",
                        field="oem_authorization_certificate",
                        operator="EXISTS",
                        expected_value="OEM Authorization Certificate",
                        mandatory=True,
                        evidence_block_ids=c.evidence_block_ids,
                        source_clause=c.source_clause or "Document required from seller",
                        applicability=c.applicability,
                        extraction_confidence=c.extraction_confidence,
                        requirement_type="BIDDER_COMPLIANCE",
                        source_pass=c.source_pass,
                    ))
                if "compliance of boq" in combined_text:
                    decomposed.append(CandidateRequirement(
                        description="Compliance of BoQ specification and supporting document required from seller",
                        category="TECHNICAL_SPECIFICATION",
                        field="boq_compliance_document",
                        operator="EXISTS",
                        expected_value="Compliance of BoQ specification and supporting document",
                        mandatory=True,
                        evidence_block_ids=c.evidence_block_ids,
                        source_clause=c.source_clause or "Document required from seller",
                        applicability=c.applicability,
                        extraction_confidence=c.extraction_confidence,
                        requirement_type="BIDDER_COMPLIANCE",
                        source_pass=c.source_pass,
                    ))
                if ("seeking exemption" in combined_text or "*" in (desc + val_str)) and not any(d.field == "exemption_supporting_documents" for d in decomposed):
                    decomposed.append(CandidateRequirement(
                        description="Supporting documents to prove eligibility for exemption from Experience / Turnover Criteria must be uploaded for evaluation by buyer",
                        category="STATUTORY_ELIGIBILITY",
                        field="exemption_supporting_documents",
                        operator="EXISTS",
                        expected_value="Supporting documents to prove eligibility for exemption must be uploaded",
                        mandatory=True,
                        evidence_block_ids=c.evidence_block_ids,
                        source_clause="Footnote / Proviso",
                        applicability=c.applicability,
                        extraction_confidence=c.extraction_confidence,
                        requirement_type="BIDDER_COMPLIANCE",
                        source_pass=c.source_pass,
                    ))
            else:
                decomposed.append(c)

        return decomposed

    def _merge_and_deduplicate_candidates(self, candidates: List[CandidateRequirement]) -> List[CandidateRequirement]:
        merged: List[CandidateRequirement] = []

        for c in candidates:
            c_blocks = set(c.evidence_block_ids or [])
            c_fld = re.sub(r"[_\s\-]+", "", str(c.field or "").lower())
            c_val = re.sub(r"[_\s\-]+", "", str(c.expected_value or "").lower())

            matched_idx = -1
            for idx, existing in enumerate(merged):
                e_blocks = set(existing.evidence_block_ids or [])
                e_fld = re.sub(r"[_\s\-]+", "", str(existing.field or "").lower())
                e_val = re.sub(r"[_\s\-]+", "", str(existing.expected_value or "").lower())

                # Exact match on field and expected value with block overlap (or if either has no blocks)
                if c_fld and e_fld and c_fld == e_fld and c_val == e_val:
                    if not c_blocks or not e_blocks or bool(c_blocks.intersection(e_blocks)):
                        matched_idx = idx
                        break

                # Also match if exact block set, field, and value match
                if c_blocks and e_blocks and c_blocks == e_blocks and c_fld == e_fld and c_val == e_val:
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                existing = merged[matched_idx]
                if not existing.mandatory and c.mandatory:
                    existing.mandatory = True
                if existing.requirement_type != "BIDDER_COMPLIANCE" and c.requirement_type == "BIDDER_COMPLIANCE":
                    existing.requirement_type = "BIDDER_COMPLIANCE"
                if len(c.description or "") > len(existing.description or ""):
                    existing.description = c.description
                if not existing.source_clause and c.source_clause:
                    existing.source_clause = c.source_clause
                for b in (c.evidence_block_ids or []):
                    if b not in existing.evidence_block_ids:
                        existing.evidence_block_ids.append(b)
            else:
                merged.append(CandidateRequirement(
                    description=c.description,
                    category=c.category,
                    field=c.field,
                    operator=c.operator,
                    expected_value=c.expected_value,
                    mandatory=c.mandatory,
                    evidence_block_ids=list(c.evidence_block_ids or []),
                    source_clause=c.source_clause,
                    applicability=c.applicability,
                    extraction_confidence=c.extraction_confidence,
                    requirement_type=c.requirement_type,
                    source_pass=c.source_pass,
                ))

        return merged

    def _parse_candidates(
        self,
        response_text: str,
        default_source_pass: Optional[str] = None
    ) -> List[CandidateRequirement]:
        try:
            cleaned = response_text.strip()
            # Clean markdown formatting if present
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            data = json.loads(cleaned.strip())
            req_list = data.get("requirements", [])
            candidates = []
            for item in req_list:
                candidates.append(CandidateRequirement(
                    description=item.get("description", ""),
                    category=item.get("category", "OTHER"),
                    field=item.get("field"),
                    operator=item.get("operator", "=="),
                    expected_value=item.get("expected_value"),
                    mandatory=item.get("mandatory", True),
                    evidence_block_ids=item.get("evidence_block_ids", []),
                    source_clause=item.get("source_clause"),
                    applicability=item.get("applicability"),
                    extraction_confidence=item.get("extraction_confidence", "HIGH"),
                    requirement_type=item.get("requirement_type", "BIDDER_COMPLIANCE"),
                    source_pass=item.get("source_pass", default_source_pass),
                ))
            return candidates
        except Exception:
            return []

    def _normalize_expected_value(self, val: Any, field_name: Optional[str]) -> Tuple[Any, Optional[str]]:
        if val is None:
            return None, None

        if isinstance(val, bool):
            return val, "BOOLEAN"

        val_str = str(val).strip()

        # Boolean strings (e.g. EMD: No, ePBG: No, MII Preference: No)
        if val_str.lower() in ("no", "not required", "not applicable", "none", "false"):
            return False, "BOOLEAN"
        if val_str.lower() in ("yes", "required", "true"):
            return True, "BOOLEAN"

        # Currency / turnover
        if field_name and "turnover" in field_name.lower():
            curr_val, u = normalize_currency(val_str)
            if curr_val is not None:
                return float(curr_val), u or "INR"

        # Duration / warranty
        if field_name and ("warranty" in field_name.lower() or "duration" in field_name.lower()):
            dur_val, u = normalize_duration(val_str)
            if dur_val is not None:
                return int(dur_val), u or "MONTHS"

        # Numeric / delivery days
        if field_name and "delivery" in field_name.lower():
            dur_val, u = normalize_duration(val_str, target_unit="DAYS")
            if dur_val is not None:
                return int(dur_val), u or "DAYS"
            num_val, u = normalize_numeric(val_str)
            if num_val is not None:
                return int(num_val), u or "DAYS"

        # Fallback numeric
        num_val, u = normalize_numeric(val_str)
        if num_val is not None:
            norm = float(num_val) if "." in str(num_val) else int(num_val)
            return norm, u

        return val_str, None

