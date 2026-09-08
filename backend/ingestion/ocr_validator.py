# -*- coding: utf-8 -*-
"""
Deterministic OCR Output Quality Validator.
Evaluates raw OCR text output against structural sanity checks:
- Character count and density
- Printable character ratio (mojibake / corrupted glyph detection)
- Alphanumeric ratio (noise speckle / random symbol filter)
- Abnormal repetition ratio (scanner artifact / barcode line filter)
- Procurement pattern / token density
- Raw OCR engine confidence

Classifies OCR output into:
- ACCEPTED: Plausible, usable text blocks.
- LOW_CONFIDENCE: Marginally readable; flags warnings for downstream review.
- FAILED: Corrupted or garbage OCR; strictly discarded to prevent manufacturing positive facts.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
import string
from typing import Any, Dict, List, Optional

from .models import TextBlock


class OCRValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    FAILED = "FAILED"


# Regex patterns commonly found in valid procurement bids and tenders
PROCUREMENT_PATTERNS = [
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|cr|crore|lakh|inr|rs|days|months|years|qty|nos|meters)?\b", re.IGNORECASE),
    re.compile(r"\b(?:tender|bid|bidder|gem|gst|gstin|pan|cin|udyam|oem|nsic|clause|turnover|experience|delivery)\b", re.IGNORECASE),
    re.compile(r"\b(?:compliance|specification|technical|financial|schedule|section|annexure|declaration)\b", re.IGNORECASE),
    re.compile(r"\b(?:pvt|ltd|limited|corporation|enterprises|solutions|technologies|company)\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"),  # dates
]


@dataclass
class OCRQualityReport:
    """
    Deterministic validation summary of an OCR execution pass.
    """
    status: OCRValidationStatus
    confidence: float
    char_count: int
    word_count: int
    printable_ratio: float
    alpha_num_ratio: float
    repetition_ratio: float
    whitespace_ratio: float
    procurement_token_score: float
    composite_score: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "confidence": round(self.confidence, 4),
            "char_count": self.char_count,
            "word_count": self.word_count,
            "printable_ratio": round(self.printable_ratio, 4),
            "alpha_num_ratio": round(self.alpha_num_ratio, 4),
            "repetition_ratio": round(self.repetition_ratio, 4),
            "whitespace_ratio": round(self.whitespace_ratio, 4),
            "procurement_token_score": round(self.procurement_token_score, 4),
            "composite_score": round(self.composite_score, 4),
            "reasons": self.reasons,
        }


def compute_max_character_repetition(text: str) -> float:
    """
    Computes ratio of longest contiguous sequence of a single character vs total length.
    E.g. "============" or "........" or "|||||||||".
    """
    if not text:
        return 0.0

    max_streak = 1
    curr_streak = 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1]:
            curr_streak += 1
            if curr_streak > max_streak:
                max_streak = curr_streak
        else:
            curr_streak = 1

    return float(max_streak) / float(len(text))


def evaluate_procurement_token_score(text: str) -> float:
    """
    Evaluates whether the extracted text exhibits semantic procurement patterns
    (clause numbering, numbers, currencies, tender terms, dates).
    Returns score 0.0 to 1.0.
    """
    if not text or len(text.strip()) < 10:
        return 0.0

    matches = 0
    for pattern in PROCUREMENT_PATTERNS:
        if pattern.search(text):
            matches += 1

    return min(1.0, float(matches) / 3.0)


def validate_ocr_result(
    text: str,
    blocks: Optional[List[TextBlock]] = None,
    ocr_confidence: float = 0.85,
) -> OCRQualityReport:
    """
    Validates OCR text output and assigns an authoritative quality classification.
    """
    cleaned = text.strip() if text else ""
    char_len = len(cleaned)
    raw_len = len(text) if text else 0
    reasons: List[str] = []

    if char_len == 0:
        return OCRQualityReport(
            status=OCRValidationStatus.FAILED,
            confidence=0.0,
            char_count=0,
            word_count=0,
            printable_ratio=0.0,
            alpha_num_ratio=0.0,
            repetition_ratio=0.0,
            whitespace_ratio=0.0,
            procurement_token_score=0.0,
            composite_score=0.0,
            reasons=["OCR produced zero characters (empty page)."],
        )

    words = cleaned.split()
    word_count = len(words)

    # 1. Printable character ratio
    printable_chars = sum(1 for c in cleaned if c in string.printable or ord(c) > 127)
    printable_ratio = printable_chars / char_len

    # 2. Alphanumeric ratio (distinguishes text from pure noise speckles)
    alnum_chars = sum(1 for c in cleaned if c.isalnum())
    alnum_ratio = alnum_chars / char_len

    # 3. Repetition ratio
    repetition_ratio = compute_max_character_repetition(cleaned)

    # 4. Whitespace ratio
    whitespace_chars = sum(1 for c in text if c.isspace())
    whitespace_ratio = whitespace_chars / raw_len if raw_len > 0 else 0.0

    # 5. Procurement pattern score
    procurement_score = evaluate_procurement_token_score(cleaned)

    # 6. Composite quality score
    # Normalized length factor up to 150 chars
    length_factor = min(1.0, float(char_len) / 150.0)
    conf_factor = max(0.1, min(1.0, ocr_confidence))

    composite = (
        0.35 * conf_factor +
        0.25 * alnum_ratio +
        0.25 * procurement_score +
        0.15 * length_factor
    ) * printable_ratio

    # Penalize extreme character repetition
    if repetition_ratio > 0.35:
        composite *= 0.5
        reasons.append(f"Abnormal character streak detected ({repetition_ratio:.1%} of text is identical consecutive characters).")

    # Defect evaluations
    if printable_ratio < 0.70:
        reasons.append(f"Severely corrupted text encoding (printable ratio {printable_ratio:.1%} < 70%).")

    if alnum_ratio < 0.20:
        reasons.append(f"Excessive symbol / speckle noise (alphanumeric ratio {alnum_ratio:.1%} < 20%).")

    if char_len < 10:
        reasons.append(f"Extremely low text volume ({char_len} characters < 10 threshold).")

    if conf_factor < 0.40:
        reasons.append(f"Low engine word confidence ({conf_factor:.1%} < 40%).")

    # Status determination
    if (
        char_len < 10
        or printable_ratio < 0.70
        or alnum_ratio < 0.20
        or repetition_ratio > 0.50
        or composite < 0.25
    ):
        status = OCRValidationStatus.FAILED
        if not reasons:
            reasons.append("OCR output failed deterministic quality thresholds.")
    elif (
        char_len < 30
        or alnum_ratio < 0.40
        or conf_factor < 0.50
        or composite < 0.50
    ):
        status = OCRValidationStatus.LOW_CONFIDENCE
        if not reasons:
            reasons.append("Marginal OCR confidence; manual officer review recommended.")
    else:
        status = OCRValidationStatus.ACCEPTED
        reasons.append("OCR output meets character density, vocabulary plausibility, and confidence criteria.")

    return OCRQualityReport(
        status=status,
        confidence=conf_factor,
        char_count=char_len,
        word_count=word_count,
        printable_ratio=printable_ratio,
        alpha_num_ratio=alnum_ratio,
        repetition_ratio=repetition_ratio,
        whitespace_ratio=whitespace_ratio,
        procurement_token_score=procurement_score,
        composite_score=composite,
        reasons=reasons,
    )
