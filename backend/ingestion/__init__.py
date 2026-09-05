# -*- coding: utf-8 -*-
from .bbox import convert_pymupdf_to_contract_bbox, validate_bbox
from .confidence import evaluate_page_extraction_quality
from .evidence import build_evidence_from_block, find_evidence_for_keyword
from .fact_extractor_interface import BaseFactExtractor, RuleBasedFactExtractor
from .models import (
    DocumentMetadata,
    DocumentType,
    EvidenceReference,
    ExtractedPage,
    ExtractionMethod,
    ExtractionResult,
    TextBlock,
)
from .ocr import BaseOCREngine, MockOCREngine, OCRPageResult, TesseractOCREngine
from .page_segmenter import classify_document_type
from .pipeline import DocumentIngestionPipeline

__all__ = [
    "convert_pymupdf_to_contract_bbox",
    "validate_bbox",
    "evaluate_page_extraction_quality",
    "build_evidence_from_block",
    "find_evidence_for_keyword",
    "BaseFactExtractor",
    "RuleBasedFactExtractor",
    "DocumentMetadata",
    "DocumentType",
    "EvidenceReference",
    "ExtractedPage",
    "ExtractionMethod",
    "ExtractionResult",
    "TextBlock",
    "BaseOCREngine",
    "TesseractOCREngine",
    "MockOCREngine",
    "OCRPageResult",
    "classify_document_type",
    "DocumentIngestionPipeline",
]
