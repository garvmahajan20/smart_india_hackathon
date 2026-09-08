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
from .ocr_validator import OCRQualityReport, OCRValidationStatus, validate_ocr_result
from .page_segmenter import classify_document_type
from .pipeline import DocumentIngestionPipeline
from .preprocessing import (
    PreprocessedImageResult,
    map_ocr_bbox_to_page_coordinates,
    preprocess_image_for_ocr,
)
from .quality_assessment import (
    PageQualityAssessment,
    PageQualityGrade,
    assess_page_quality,
)

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
    "PageQualityGrade",
    "PageQualityAssessment",
    "assess_page_quality",
    "PreprocessedImageResult",
    "preprocess_image_for_ocr",
    "map_ocr_bbox_to_page_coordinates",
    "OCRValidationStatus",
    "OCRQualityReport",
    "validate_ocr_result",
]
