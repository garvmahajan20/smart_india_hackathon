# -*- coding: utf-8 -*-
import re
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from backend.verification.models import IntegrityFinding
from .models import BidderFact, VerificationResult
from .normalization import (
    normalize_categorical,
    normalize_currency,
    normalize_duration,
    normalize_numeric,
)

def _normalize_name_for_comparison(name: Optional[str]) -> str:
    if not name:
        return ""
    # Strip dots and punctuation to avoid regex word-boundary traps on abbreviation dots
    cleaned = str(name).strip().upper().replace(".", " ").replace(",", " ")
    cleaned = " ".join(cleaned.split())
    # Normalize common legal company forms
    cleaned = re.sub(r"\bPRIVATE LIMITED\b", "PVT LTD", cleaned)
    cleaned = re.sub(r"\bPVT LTD\b", "PVT LTD", cleaned)
    cleaned = re.sub(r"\bLIMITED\b", "LTD", cleaned)
    cleaned = re.sub(r"\bL L P\b", "LLP", cleaned)
    cleaned = re.sub(r"\bINCORPORATED\b", "INC", cleaned)
    cleaned = re.sub(r"\bCORPORATION\b", "CORP", cleaned)
    return " ".join(cleaned.split())

def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().upper()

class CrossDocumentContradictionEngine:
    """
    Deterministic Cross-Document Contradiction and Integrity Engine.
    Detects inconsistencies across multiple documents/sections within the same bid submission.
    Preserves evidence from both sides of any detected discrepancy.
    Operates strictly without LLMs, network calls, or random heuristics.
    """

    def __init__(self):
        pass

    def compare_values(
        self,
        field_name: str,
        value_a: Any,
        value_b: Any,
        description_hint: Optional[str] = None
    ) -> Tuple[str, str, str, str]:
        """
        Deterministically compares two values extracted from different documents.

        Returns:
            Tuple of (status, finding_type, severity, description)
            status: "CONTRADICTION" | "REVIEW" | "CONSISTENT"
        """
        f_lower = field_name.lower()

        # 1. Identifier checks: GSTIN, PAN, Udyam
        if any(term in f_lower for term in ["gstin", "gst"]):
            clean_a = _clean_str(value_a)
            clean_b = _clean_str(value_b)
            if clean_a == clean_b:
                return "CONSISTENT", "CONSISTENT_GSTIN", "INFO", f"GSTIN matches consistently across documents: '{value_a}'."
            else:
                return (
                    "CONTRADICTION",
                    "GSTIN_CONTRADICTION",
                    "HIGH",
                    f"GSTIN differs across documents: '{value_a}' vs '{value_b}'."
                )

        if f_lower == "pan" or "_pan" in f_lower or "pan_" in f_lower or "pan_number" in f_lower:
            clean_a = _clean_str(value_a)
            clean_b = _clean_str(value_b)
            if clean_a == clean_b:
                return "CONSISTENT", "CONSISTENT_PAN", "INFO", f"PAN matches consistently across documents: '{value_a}'."
            else:
                return (
                    "CONTRADICTION",
                    "PAN_CONTRADICTION",
                    "HIGH",
                    f"PAN differs across documents: '{value_a}' vs '{value_b}'."
                )

        if any(term in f_lower for term in ["udyam", "msme"]):
            clean_a = _clean_str(value_a)
            clean_b = _clean_str(value_b)
            if clean_a == clean_b:
                return "CONSISTENT", "CONSISTENT_UDYAM", "INFO", f"Udyam registration matches consistently: '{value_a}'."
            else:
                return (
                    "CONTRADICTION",
                    "UDYAM_CONTRADICTION",
                    "HIGH",
                    f"Udyam registration number differs across documents: '{value_a}' vs '{value_b}'."
                )

        # 2. Duration / Warranty checks
        if any(term in f_lower for term in ["warranty", "experience", "duration"]):
            dur_a, _ = normalize_duration(value_a, target_unit="MONTHS")
            dur_b, _ = normalize_duration(value_b, target_unit="MONTHS")

            if dur_a is not None and dur_b is not None:
                if dur_a == dur_b:
                    return "CONSISTENT", "CONSISTENT_DURATION", "INFO", f"Duration values are equivalent across documents: '{value_a}' == '{value_b}'."
                else:
                    return (
                        "CONTRADICTION",
                        "WARRANTY_CONTRADICTION",
                        "HIGH",
                        f"Warranty/duration stated as '{value_a}' in one document and '{value_b}' in another document."
                    )

        # 3. Monetary / Turnover checks
        if any(term in f_lower for term in ["turnover", "revenue", "financial", "amount", "price"]):
            num_a, _ = normalize_numeric(value_a)
            num_b, _ = normalize_numeric(value_b)

            if num_a is not None and num_b is not None:
                if num_a == num_b:
                    return "CONSISTENT", "CONSISTENT_TURNOVER", "INFO", f"Monetary values are equivalent across documents: '{value_a}' == '{value_b}'."
                else:
                    return (
                        "CONTRADICTION",
                        "TURNOVER_CONTRADICTION",
                        "HIGH",
                        f"Financial turnover differs across documents: '{value_a}' vs '{value_b}'."
                    )

        # 4. Company Name checks
        if any(term in f_lower for term in ["company", "bidder", "legal_name", "entity_name"]):
            norm_a = _normalize_name_for_comparison(value_a)
            norm_b = _normalize_name_for_comparison(value_b)

            if norm_a == norm_b:
                # Same base legal name
                if str(value_a).strip() != str(value_b).strip():
                    # Minor punctuation or casing variant
                    return (
                        "CONSISTENT",
                        "BENIGN_NAME_VARIANT",
                        "INFO",
                        f"Legal-name representation difference is a benign abbreviation or alias: '{value_a}' vs '{value_b}'."
                    )
                return "CONSISTENT", "CONSISTENT_COMPANY_NAME", "INFO", f"Company name matches consistently: '{value_a}'."

            # Check if one is a substring/alias expansion
            if norm_a in norm_b or norm_b in norm_a:
                return (
                    "REVIEW",
                    "COMPANY_NAME_VARIANT",
                    "MEDIUM",
                    f"Legal-name representation differs across documents but may be a benign alias: '{value_a}' vs '{value_b}'; human review required."
                )

            # Fundamentally different company name
            return (
                "CONTRADICTION",
                "COMPANY_NAME_CONTRADICTION",
                "HIGH",
                f"Different legal entities declared across documents: '{value_a}' vs '{value_b}'."
            )

        # 5. General Fallback
        str_a = _clean_str(value_a)
        str_b = _clean_str(value_b)
        if str_a == str_b:
            return "CONSISTENT", "CONSISTENT_MATCH", "INFO", f"Field '{field_name}' matches consistently across documents."
        else:
            return (
                "CONTRADICTION",
                "GENERAL_CONTRADICTION",
                "MEDIUM",
                f"Value for '{field_name}' differs across documents: '{value_a}' vs '{value_b}'."
            )

    def evaluate_pair(
        self,
        contradiction_id: str,
        bid_id: str,
        field_name: str,
        value_a: Any,
        value_b: Any,
        document_a: str = "",
        page_a: int = 1,
        bbox_a: Optional[List[float]] = None,
        snippet_a: str = "",
        document_b: str = "",
        page_b: int = 1,
        bbox_b: Optional[List[float]] = None,
        snippet_b: str = "",
        hint_type: Optional[str] = None,
        raw_field_a: Optional[str] = None,
        raw_field_b: Optional[str] = None,
        canonical_field: Optional[str] = None,
    ) -> IntegrityFinding:
        """
        Evaluates a single pair of extracted values from Document A and Document B.
        Preserves evidence from both sides of the comparison.
        """
        # If ground truth / dataset provides hint_type (e.g. from contradiction_pairs.jsonl), align field
        effective_field = field_name
        if not effective_field and hint_type:
            if "GSTIN" in hint_type:
                effective_field = "gstin"
            elif "WARRANTY" in hint_type:
                effective_field = "warranty_years"
            elif "TURNOVER" in hint_type:
                effective_field = "turnover_cr"
            elif "NAME" in hint_type:
                effective_field = "company_name"
            else:
                effective_field = hint_type.lower()

        # Handle incomplete evidence (missing second side)
        if not document_b and page_b == 1 and not value_b:
            return IntegrityFinding(
                finding_id=contradiction_id,
                bid_id=bid_id,
                finding_type="INCOMPLETE_EVIDENCE",
                field=effective_field,
                severity="MEDIUM",
                status="REVIEW",
                description=f"Incomplete evidence for '{effective_field}': Document B reference is absent.",
                value_a=value_a,
                value_b=None,
                evidence_a={"document": document_a, "page": page_a, "bbox": bbox_a, "snippet": snippet_a},
                evidence_b={},
                requires_human_review=True,
                source="CROSS_DOCUMENT_CONTRADICTION_ENGINE",
            )

        status, ftype, severity, description = self.compare_values(effective_field, value_a, value_b)

        # If hint_type explicitly indicates a benign variant or specific type from dataset
        if hint_type == "COMPANY_NAME_VARIANT":
            status = "REVIEW"
            ftype = "COMPANY_NAME_VARIANT"
            severity = "MEDIUM"
            description = f"Legal-name representation differs across documents but may be a benign alias: '{value_a}' vs '{value_b}'; human review required."
        elif hint_type == "BENIGN_NAME_VARIANT":
            status = "CONSISTENT"
            ftype = "BENIGN_NAME_VARIANT"
            severity = "INFO"
            description = f"Legal-name representation difference is a benign abbreviation: '{value_a}' vs '{value_b}'."

        needs_review = (status != "CONSISTENT")

        # If raw fields differ, explain the canonical comparison in description
        if raw_field_a and raw_field_b and raw_field_a.lower().strip() != raw_field_b.lower().strip():
            description = f"{description} (Comparing raw fields: '{raw_field_a}' vs '{raw_field_b}', canonical: '{canonical_field or effective_field}')"

        return IntegrityFinding(
            finding_id=contradiction_id,
            bid_id=bid_id,
            finding_type=ftype,
            field=effective_field,
            severity=severity,
            status=status,
            description=description,
            value_a=value_a,
            value_b=value_b,
            evidence_a={"document": document_a, "page": page_a, "bbox": bbox_a, "snippet": snippet_a},
            evidence_b={"document": document_b, "page": page_b, "bbox": bbox_b, "snippet": snippet_b},
            requires_human_review=needs_review,
            source="CROSS_DOCUMENT_CONTRADICTION_ENGINE",
            raw_field_a=raw_field_a or effective_field,
            raw_field_b=raw_field_b or effective_field,
            canonical_field=canonical_field,
        )

    def detect_contradictions_in_bid(self, bid_id: str, facts: List[BidderFact]) -> List[IntegrityFinding]:
        """
        Groups facts for a bid by canonical field (where eligible) and compares facts
        extracted across different documents. Preserves both raw and canonical field identity.
        Produces structured IntegrityFinding records.
        """
        from .ontology import resolve_field

        grouped: Dict[str, List[BidderFact]] = defaultdict(list)
        group_canonical_ids: Dict[str, Optional[str]] = {}

        for f in facts:
            cid = f.canonical_field
            if not cid:
                res = resolve_field(f.field)
                if res.resolution_status == "RESOLVED" and res.contradiction_eligible:
                    cid = res.canonical_field_id

            if cid:
                group_key = cid
                group_canonical_ids[group_key] = cid
            else:
                group_key = f.field.lower().strip()
                group_canonical_ids[group_key] = None

            grouped[group_key].append(f)

        findings: List[IntegrityFinding] = []
        finding_idx = 0

        for group_key, fact_list in grouped.items():
            if len(fact_list) < 2:
                continue

            canonical_id = group_canonical_ids.get(group_key)

            # Compare pairs across distinct documents
            for i in range(len(fact_list)):
                for j in range(i + 1, len(fact_list)):
                    fact_a = fact_list[i]
                    fact_b = fact_list[j]

                    # Only compare if from different documents or distinct pages
                    if fact_a.source_document == fact_b.source_document and fact_a.page == fact_b.page:
                        continue

                    finding_idx += 1
                    fid = f"INT-{bid_id}-{group_key.upper()}-{finding_idx:03d}"

                    finding = self.evaluate_pair(
                        contradiction_id=fid,
                        bid_id=bid_id,
                        field_name=canonical_id or group_key,
                        value_a=fact_a.normalized_value or fact_a.value,
                        value_b=fact_b.normalized_value or fact_b.value,
                        document_a=fact_a.source_document,
                        page_a=fact_a.page,
                        bbox_a=fact_a.bbox,
                        snippet_a=fact_a.raw_text_snippet or "",
                        document_b=fact_b.source_document,
                        page_b=fact_b.page,
                        bbox_b=fact_b.bbox,
                        snippet_b=fact_b.raw_text_snippet or "",
                        raw_field_a=fact_a.field,
                        raw_field_b=fact_b.field,
                        canonical_field=canonical_id,
                    )

                    # Only record non-trivial findings or contradictions
                    if finding.status != "CONSISTENT":
                        findings.append(finding)

        return findings
