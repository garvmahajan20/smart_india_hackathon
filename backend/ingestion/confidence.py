# -*- coding: utf-8 -*-
import string
from typing import Dict, List, Tuple

# Quality heuristic thresholds
MIN_CHARS_FOR_NORMAL_PAGE = 80
MIN_CHARS_FOR_LOW_TEXT = 20
MIN_PRINTABLE_RATIO = 0.85

def evaluate_page_extraction_quality(
    text: str,
    blocks_count: int,
    is_ocr: bool = False,
    ocr_confidence: float = 1.0
) -> Tuple[str, float, bool, bool, List[str]]:
    """
    Evaluates extraction quality for an extracted page using a deterministic heuristic.

    CRITICAL TERMINOLOGY NOTICE:
    This is strictly an extraction-quality heuristic assessing optical/text clarity.
    It is NOT an AI confidence score, calibrated probability, compliance metric, or fraud indicator.

    Args:
        text: Extracted page text.
        blocks_count: Total text blocks discovered on page.
        is_ocr: True if extracted via OCR, False if native PDF.
        ocr_confidence: Raw OCR confidence (0.0 - 1.0) if applicable.

    Returns:
        Tuple of (confidence_str, quality_score, is_empty, is_low_text, warnings)
        confidence_str: "HIGH" | "MEDIUM" | "LOW"
        quality_score: 0.0 - 1.0
        is_empty: bool
        is_low_text: bool
        warnings: List[str]
    """
    warnings: List[str] = []
    cleaned = text.strip()
    char_count = len(cleaned)

    if char_count == 0 or blocks_count == 0:
        return "LOW", 0.0, True, True, ["Page is empty or contains zero text blocks."]

    # Calculate printable character ratio (detects font encoding errors / mojibake / corrupted glyphs)
    printable_chars = sum(1 for c in cleaned if c in string.printable or ord(c) > 127)
    printable_ratio = printable_chars / char_count if char_count > 0 else 0.0

    if printable_ratio < MIN_PRINTABLE_RATIO:
        warnings.append(f"Low printable character ratio ({printable_ratio:.2%}); possible font encoding anomaly.")

    is_low = char_count < MIN_CHARS_FOR_LOW_TEXT
    if is_low:
        warnings.append(f"Low text volume ({char_count} characters); page may be an image, cover, or scan.")

    # Base heuristic scoring
    if is_ocr:
        base_score = max(0.2, min(1.0, ocr_confidence))
        if is_low:
            base_score *= 0.5
    else:
        # Native PDF extraction
        if char_count >= MIN_CHARS_FOR_NORMAL_PAGE and printable_ratio >= MIN_PRINTABLE_RATIO:
            base_score = 0.95
        elif char_count >= MIN_CHARS_FOR_LOW_TEXT:
            base_score = 0.70
        else:
            base_score = 0.35

    score = base_score * printable_ratio

    if score >= 0.80:
        category = "HIGH"
    elif score >= 0.50:
        category = "MEDIUM"
    else:
        category = "LOW"

    return category, round(score, 4), False, is_low, warnings
