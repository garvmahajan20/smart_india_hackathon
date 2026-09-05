# -*- coding: utf-8 -*-
import os
import re
from typing import List, Optional

from .models import DocumentType

def classify_document_type(
    filename: str,
    file_path: str = "",
    preview_text: str = ""
) -> DocumentType:
    """
    Deterministically classifies document type based on path, filename, and header cues.
    Strictly defaults to UNKNOWN when uncertain.
    """
    name_lower = os.path.basename(filename or file_path).lower()
    path_lower = file_path.lower()
    text_sample = preview_text[:300].lower() if preview_text else ""

    # Check path or filename metadata first
    if "/tenders/" in path_lower or "\\tenders\\" in path_lower or name_lower.startswith("tender-"):
        return DocumentType.TENDER

    if "/bids/" in path_lower or "\\bids\\" in path_lower or name_lower.startswith("bid-"):
        return DocumentType.BID

    # Real-world GeM / NIT patterns
    if name_lower.startswith("gem_") or name_lower.startswith("nit") or "tender" in name_lower:
        return DocumentType.TENDER

    if "technical" in name_lower or "tech_bid" in name_lower or "technical bid" in text_sample:
        return DocumentType.TECHNICAL_BID

    if "financial" in name_lower or "boq" in name_lower or "price_bid" in name_lower:
        return DocumentType.FINANCIAL_BID

    if any(k in name_lower for k in ["cert", "udyam", "iso", "pan", "gst"]):
        return DocumentType.CERTIFICATE

    if any(k in name_lower for k in ["decl", "undertaking", "affidavit"]):
        return DocumentType.DECLARATION

    return DocumentType.UNKNOWN
