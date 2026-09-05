# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, List, Optional

from .models import EvidenceReference, ExtractedPage, TextBlock

def build_evidence_from_block(
    document_name: str,
    block: TextBlock,
    extraction_method: str = "NATIVE_PDF_PARSING",
    extraction_confidence: str = "HIGH"
) -> EvidenceReference:
    """
    Constructs an EvidenceReference directly from an extracted TextBlock.
    Strictly preserves block coordinates in [ymin, xmin, ymax, xmax] format.
    """
    return EvidenceReference(
        document=document_name,
        page=block.page_number,
        bbox=block.bbox,
        snippet=block.text.strip(),
        extraction_method=extraction_method,
        extraction_confidence=extraction_confidence,
        block_id=block.block_id,
    )

def find_evidence_for_keyword(
    document_name: str,
    pages: List[ExtractedPage],
    keyword_or_pattern: str,
    is_regex: bool = False
) -> Optional[EvidenceReference]:
    """
    Scans extracted pages to locate the most relevant text block containing
    the target keyword or regex pattern, returning an EvidenceReference.
    """
    for page in pages:
        for block in page.blocks:
            match = False
            if is_regex:
                if re.search(keyword_or_pattern, block.text, re.IGNORECASE):
                    match = True
            else:
                if keyword_or_pattern.lower() in block.text.lower():
                    match = True

            if match:
                method_name = "OCR_TEXT_EXTRACTION" if page.extraction_method.value == "OCR" else "NATIVE_PDF_PARSING"
                return build_evidence_from_block(
                    document_name=document_name,
                    block=block,
                    extraction_method=method_name,
                    extraction_confidence=page.extraction_confidence,
                )
    return None
