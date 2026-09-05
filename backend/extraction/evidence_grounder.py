# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.normalization import (
    normalize_boolean,
    normalize_currency,
    normalize_duration,
    normalize_numeric,
)
from backend.ingestion.models import ExtractionResult, TextBlock
from .models import ExtractionStatus, GroundingValidationResult

STOP_WORDS = {
    "the", "and", "of", "for", "with", "shall", "must", "is", "are", "in", "to",
    "a", "an", "on", "at", "by", "from", "as", "be", "this", "that", "it", "or"
}

def verify_fact_support(
    raw_value: Any,
    field_name: str,
    combined_text: str,
) -> Tuple[bool, str, List[str]]:
    """
    Deterministically verifies that an extracted candidate fact's value is actually
    supported by the cited physical TextBlock(s) text.
    Returns (is_supported, match_type, list_of_error_messages).
    """
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return False, "EMPTY_VALUE", ["Extracted value is empty or null."]

    text_lower = combined_text.lower()
    val_str = str(raw_value).strip()
    val_lower = val_str.lower()
    field_lower = field_name.lower()

    # 1. Identifiers (GSTIN, PAN, Udyam, CIN, Registration Numbers)
    if any(k in field_lower for k in ["gstin", "pan", "udyam", "cin", "registration", "cert_number"]):
        val_alpha = re.sub(r"[^A-Z0-9]", "", val_str.upper())
        text_alpha = re.sub(r"[^A-Z0-9]", "", combined_text.upper())
        if len(val_alpha) >= 3 and val_alpha in text_alpha:
            return True, "EXACT_IDENTIFIER_MATCH", []
        return False, "IDENTIFIER_MISMATCH", [f"Extracted identifier '{raw_value}' not found in source text blocks."]

    # 2. Durations (years, months, days)
    is_duration_field = any(k in field_lower for k in ["warranty", "experience", "validity", "delivery", "duration"])
    has_duration_unit = bool(re.search(r"\b(years?|yrs?|yr|months?|mths?|mth|mo|days?|d)\b", val_lower))
    if is_duration_field or has_duration_unit:
        cand_m, _ = normalize_duration(raw_value, target_unit="MONTHS")
        cand_d, _ = normalize_duration(raw_value, target_unit="DAYS")
        if cand_m is not None or cand_d is not None:
            # Look for duration patterns in text
            dur_matches = re.findall(
                r"\b(\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s*(years?|yrs?|yr|months?|mths?|mth|mo|days?|d)\b",
                text_lower
            )
            for num_part, unit_part in dur_matches:
                phrase = f"{num_part} {unit_part}"
                t_m, _ = normalize_duration(phrase, target_unit="MONTHS")
                if t_m is not None and cand_m is not None and t_m == cand_m:
                    return True, "DURATION_NORMALIZED_MATCH", []
                t_d, _ = normalize_duration(phrase, target_unit="DAYS")
                if t_d is not None and cand_d is not None and t_d == cand_d:
                    return True, "DURATION_NORMALIZED_MATCH", []
            return False, "DURATION_MISMATCH", [f"Extracted duration '{raw_value}' does not match any duration in source text."]

    # 3. Currency & Numeric (Turnover, Amount, Price, Percentage, Local Content, etc.)
    cand_curr, _ = normalize_currency(raw_value)
    cand_num, _ = normalize_numeric(raw_value)
    if cand_curr is not None or cand_num is not None:
        # Check currency phrases in text (e.g. Rs. 10 Crores, INR 12.50 Cr, 5%)
        curr_matches = re.findall(
            r"(?:rs\.?|inr|rupees|₹)?\s*(\d+(?:[.,]\d+)?)\s*(crores?|crs?|lakhs?|lacs?|millions?|thousands?|k|m|cr|%)?",
            text_lower
        )
        for num_str, scale_str in curr_matches:
            if not num_str:
                continue
            phrase = f"{num_str} {scale_str}".strip() if scale_str else num_str
            t_curr, _ = normalize_currency(phrase)
            if t_curr is not None and cand_curr is not None and t_curr == cand_curr:
                return True, "CURRENCY_MATCH", []
            t_num, _ = normalize_numeric(phrase)
            if t_num is not None and cand_num is not None and t_num == cand_num:
                return True, "NUMERIC_MATCH", []
        # Check raw digits token containment
        raw_num_match = re.search(r"[-+]?\d+(?:\.\d+)?", val_str)
        if raw_num_match:
            num_token = raw_num_match.group(0)
            if re.search(r"(?<![\d.])" + re.escape(num_token) + r"(?![\d.])", text_lower):
                return True, "NUMERIC_TOKEN_MATCH", []
        return False, "NUMERIC_MISMATCH", [f"Claimed numeric/monetary value '{raw_value}' not found in source text blocks."]

    # 4. Booleans / Affirmative Declarations (e.g. Authorized Distributor = YES)
    cand_bool = normalize_boolean(raw_value)
    if cand_bool is not None:
        if cand_bool is True:
            field_clean = re.sub(r"^(is_|has_|are_)", "", field_lower)
            filter_words = STOP_WORDS | {"status", "compliance", "undertaking", "confirmation", "cert", "certificate", "declared", "declaration"}
            tokens = [t for t in re.split(r"[_\s\-]+", field_clean) if len(t) >= 3 and t not in filter_words]
            if tokens:
                matched = [t for t in tokens if t in text_lower]
                if len(matched) == len(tokens):
                    # Check for explicit negation
                    if re.search(r"\b(not|unauthorized|non-compliant|ineligible|rejected|disqualified)\b", text_lower):
                        return False, "NEGATED_BOOLEAN", [f"Evidence text explicitly negates claim '{field_name}'."]
                    return True, "BOOLEAN_AFFIRMED", []
                elif len(matched) > 0 and (len(matched) / len(tokens)) >= 0.5:
                    return True, "BOOLEAN_PARTIAL_AFFIRMED", []
                else:
                    return False, "BOOLEAN_UNSUPPORTED", [f"Claim '{field_name}={raw_value}' has no supporting keywords in cited text."]
            else:
                if any(w in text_lower for w in ["yes", "confirmed", "submitted", "available", "compliant"]):
                    return True, "AFFIRMATIVE_WORD_FOUND", []
                return False, "BOOLEAN_UNSUPPORTED", [f"Claim '{field_name}={raw_value}' has no supporting evidence in text."]
        else:
            return True, "BOOLEAN_NEGATIVE_ACCEPTED", []

    # 5. Categorical & Textual Strings (e.g. Company Name, Make/Model, Address, Certificate Title)
    if val_lower in text_lower:
        return True, "EXACT_SUBSTRING_MATCH", []

    tokens = [t for t in re.findall(r"\b[A-Za-z0-9]+(?::[A-Za-z0-9]+)?\b", val_lower) if len(t) >= 2 and t not in STOP_WORDS]
    if not tokens:
        return False, "NO_SUBSTANTIVE_TOKENS", ["No substantive tokens in extracted textual claim."]

    matched = [t for t in tokens if t in text_lower]

    # Critical code tokens (containing digits or colons) MUST be present
    code_tokens = [t for t in tokens if any(c.isdigit() for c in t) or ":" in t]
    if code_tokens:
        if not all(c in text_lower for c in code_tokens):
            return False, "CODE_MISMATCH", [f"Specific code or number in '{raw_value}' not found in evidence text."]

    if len(matched) / len(tokens) >= 0.75:
        return True, "TOKEN_CONTAINMENT_MATCH", []

    return False, "TEXT_UNSUPPORTED", [f"Claim '{raw_value}' not supported by cited evidence text."]


class EvidenceGrounder:
    """
    Validates that LLM candidate extractions strictly ground into actual Step 6 TextBlocks.
    Prevents hallucinated coordinates, invented page numbers, or ungrounded claims.
    Preserves multi-block provenance with backward compatibility.
    """

    def __init__(self, extraction_result: ExtractionResult):
        self.extraction_result = extraction_result
        self.doc_name = extraction_result.metadata.filename
        self.doc_id = getattr(extraction_result.metadata, "document_id", self.doc_name)
        self.blocks_by_id: Dict[str, Tuple[int, TextBlock]] = {}

        # Index all blocks by block_id
        for page in extraction_result.pages:
            for block in page.blocks:
                self.blocks_by_id[block.block_id] = (page.page_number, block)

    def ground_requirement(
        self,
        candidate_block_ids: List[str],
        expected_value: Any = None,
        description: str = ""
    ) -> GroundingValidationResult:
        """
        Grounds a requirement candidate into verified Step 6 evidence blocks.
        """
        if not candidate_block_ids:
            return GroundingValidationResult(
                is_valid=False,
                status=ExtractionStatus.GROUNDING_FAILED,
                errors=["No evidence_block_ids supplied by extraction candidate."],
            )

        resolved_evidence: List[Dict[str, Any]] = []
        errors: List[str] = []
        warnings: List[str] = []

        primary_page = 1
        primary_bbox = None
        combined_snippets: List[str] = []

        # Deduplicate while preserving order
        unique_block_ids: List[str] = []
        seen_ids: Set[str] = set()
        for b_id in candidate_block_ids:
            if b_id not in seen_ids:
                seen_ids.add(b_id)
                unique_block_ids.append(b_id)
            else:
                warnings.append(f"Duplicate evidence_block_id '{b_id}' removed.")

        for block_id in unique_block_ids:
            if block_id not in self.blocks_by_id:
                errors.append(f"Referenced block_id '{block_id}' does not exist in Step 6 document ingestion result.")
                continue

            page_num, block = self.blocks_by_id[block_id]
            if primary_bbox is None:
                primary_page = page_num
                primary_bbox = block.bbox

            combined_snippets.append(block.text)
            resolved_evidence.append({
                "block_id": block.block_id,
                "document": self.doc_name,
                "document_id": self.doc_id,
                "page": page_num,
                "bbox": block.bbox,
                "snippet": block.text[:300],
                "source_type": "TENDER_CLAUSE",
            })

        if errors:
            return GroundingValidationResult(
                is_valid=False,
                status=ExtractionStatus.GROUNDING_FAILED,
                errors=errors,
                resolved_evidence=resolved_evidence,
            )

        # Check that the text actually contains supporting evidence for expected_value if string/numeric
        all_text = " ".join(combined_snippets).lower()
        if expected_value is not None:
            val_str = str(expected_value).strip().lower()
            digits = re.findall(r"\d+", val_str)
            if digits:
                if not any(d in all_text for d in digits):
                    warnings.append(f"Claimed value '{expected_value}' digits not found in source text blocks.")

        status = ExtractionStatus.REVIEW_REQUIRED if warnings else ExtractionStatus.ACCEPTED
        return GroundingValidationResult(
            is_valid=(len(errors) == 0),
            status=status,
            errors=errors,
            warnings=warnings,
            resolved_evidence=resolved_evidence,
            primary_page=primary_page,
            primary_bbox=primary_bbox,
            raw_snippet="\n".join(combined_snippets)[:500],
        )

    def ground_fact(
        self,
        candidate_block_ids: List[str],
        raw_value: Any,
        field_name: str,
        strict: bool = True,
    ) -> GroundingValidationResult:
        """
        Grounds a bidder fact candidate into verified Step 6 evidence blocks.
        Enforces strict deterministic textual and numeric support when strict=True.
        Preserves all supporting blocks in resolved_evidence for multi-block provenance.
        """
        if not candidate_block_ids:
            return GroundingValidationResult(
                is_valid=False,
                status=ExtractionStatus.GROUNDING_FAILED,
                errors=["No evidence_block_ids supplied for bidder fact."],
            )

        resolved_evidence: List[Dict[str, Any]] = []
        errors: List[str] = []
        warnings: List[str] = []

        primary_page = 1
        primary_bbox = None
        snippets: List[str] = []

        # Deduplicate while preserving order
        unique_block_ids: List[str] = []
        seen_ids: Set[str] = set()
        for b_id in candidate_block_ids:
            if b_id not in seen_ids:
                seen_ids.add(b_id)
                unique_block_ids.append(b_id)
            else:
                warnings.append(f"Duplicate evidence_block_id '{b_id}' removed.")

        for block_id in unique_block_ids:
            if block_id not in self.blocks_by_id:
                errors.append(f"Fact references unknown block_id '{block_id}'.")
                continue

            page_num, block = self.blocks_by_id[block_id]
            if primary_bbox is None:
                primary_page = page_num
                primary_bbox = block.bbox

            snippets.append(block.text)
            resolved_evidence.append({
                "block_id": block.block_id,
                "document": self.doc_name,
                "document_id": self.doc_id,
                "page": page_num,
                "bbox": block.bbox,
                "snippet": block.text[:300],
                "source_type": "BIDDER_SUBMISSION",
            })

        if errors:
            return GroundingValidationResult(
                is_valid=False,
                status=ExtractionStatus.GROUNDING_FAILED,
                errors=errors,
                resolved_evidence=resolved_evidence,
            )

        # Value support verification
        combined_text = " ".join(snippets)
        is_supported, match_type, support_errors = verify_fact_support(raw_value, field_name, combined_text)

        if not is_supported:
            if strict:
                return GroundingValidationResult(
                    is_valid=False,
                    status=ExtractionStatus.GROUNDING_FAILED,
                    errors=support_errors,
                    warnings=warnings,
                    resolved_evidence=resolved_evidence,
                    primary_page=primary_page,
                    primary_bbox=primary_bbox,
                    raw_snippet="\n".join(snippets)[:500],
                )
            else:
                warnings.extend(support_errors)
                status = ExtractionStatus.REVIEW_REQUIRED
        else:
            status = ExtractionStatus.REVIEW_REQUIRED if warnings else ExtractionStatus.ACCEPTED

        return GroundingValidationResult(
            is_valid=True,
            status=status,
            errors=errors,
            warnings=warnings,
            resolved_evidence=resolved_evidence,
            primary_page=primary_page,
            primary_bbox=primary_bbox,
            raw_snippet="\n".join(snippets)[:500],
        )

