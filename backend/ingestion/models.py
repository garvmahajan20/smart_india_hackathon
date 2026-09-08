# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class ExtractionMethod(str, Enum):
    NATIVE_PDF = "NATIVE_PDF"
    OCR = "OCR"
    HYBRID = "HYBRID"
    FAILED = "FAILED"

class DocumentType(str, Enum):
    TENDER = "TENDER"
    BID = "BID"
    TECHNICAL_BID = "TECHNICAL_BID"
    FINANCIAL_BID = "FINANCIAL_BID"
    CERTIFICATE = "CERTIFICATE"
    DECLARATION = "DECLARATION"
    UNKNOWN = "UNKNOWN"

@dataclass
class TextBlock:
    """
    Represents an atomic text block on a PDF page with bounding box coordinates.
    Bounding box strictly adheres to the contract convention: [ymin, xmin, ymax, xmax].
    """
    block_id: str
    page_number: int
    text: str
    raw_text: str
    bbox: List[float]  # [ymin, xmin, ymax, xmax]
    block_type: int = 0  # 0 for text, 1 for image
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "page_number": self.page_number,
            "text": self.text,
            "raw_text": self.raw_text,
            "bbox": self.bbox,
            "block_type": self.block_type,
            "confidence": self.confidence,
        }

@dataclass
class ExtractedPage:
    """
    Represents an independently extracted page from a document.
    """
    page_number: int
    width: float
    height: float
    text: str
    raw_text: str
    blocks: List[TextBlock] = field(default_factory=list)
    extraction_method: ExtractionMethod = ExtractionMethod.NATIVE_PDF
    extraction_confidence: str = "HIGH"  # "HIGH", "MEDIUM", "LOW"
    quality_score: float = 1.0  # Heuristic score 0.0 - 1.0
    is_empty: bool = False
    is_low_text: bool = False
    warnings: List[str] = field(default_factory=list)
    quality_grade: str = "GOOD"  # "GOOD", "DEGRADED", "SEVERELY_DEGRADED", "UNKNOWN"
    ocr_passes_count: int = 0
    preprocessing_applied: List[str] = field(default_factory=list)
    optical_signals: Dict[str, Any] = field(default_factory=dict)
    validation_report: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "text": self.text,
            "raw_text": self.raw_text,
            "blocks": [b.to_dict() for b in self.blocks],
            "extraction_method": self.extraction_method.value,
            "extraction_confidence": self.extraction_confidence,
            "quality_score": round(self.quality_score, 4),
            "is_empty": self.is_empty,
            "is_low_text": self.is_low_text,
            "warnings": self.warnings,
            "quality_grade": self.quality_grade,
            "ocr_passes_count": self.ocr_passes_count,
            "preprocessing_applied": self.preprocessing_applied,
        }
        if self.optical_signals:
            res["optical_signals"] = self.optical_signals
        if self.validation_report:
            res["validation_report"] = self.validation_report
        return res

@dataclass
class DocumentMetadata:
    """
    Metadata associated with an ingested document container.
    """
    document_id: str
    filename: str
    file_path: str
    file_size_bytes: int
    sha256: str
    page_count: int
    document_type: DocumentType = DocumentType.UNKNOWN
    bid_id: Optional[str] = None
    tender_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
            "page_count": self.page_count,
            "document_type": self.document_type.value,
            "bid_id": self.bid_id,
            "tender_id": self.tender_id,
        }

@dataclass
class ExtractionResult:
    """
    Complete structured extraction output for an ingested document.
    """
    document_id: str
    metadata: DocumentMetadata
    pages: List[ExtractedPage] = field(default_factory=list)
    overall_method: ExtractionMethod = ExtractionMethod.NATIVE_PDF
    overall_confidence: str = "HIGH"
    total_text_length: int = 0
    total_blocks: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "metadata": self.metadata.to_dict(),
            "pages": [p.to_dict() for p in self.pages],
            "overall_method": self.overall_method.value,
            "overall_confidence": self.overall_confidence,
            "total_text_length": self.total_text_length,
            "total_blocks": self.total_blocks,
            "errors": self.errors,
            "warnings": self.warnings,
        }

@dataclass
class EvidenceReference:
    """
    Evidence pointer model strictly compatible with bidder_fact.schema.json
    and verification_result.schema.json.
    """
    document: str
    page: int
    bbox: List[float]  # [ymin, xmin, ymax, xmax]
    snippet: str
    extraction_method: str = "NATIVE_PDF_PARSING"
    extraction_confidence: str = "HIGH"
    block_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "document": self.document,
            "page": self.page,
            "bbox": self.bbox,
            "snippet": self.snippet,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.extraction_confidence,
        }
        if self.block_id:
            res["block_id"] = self.block_id
        return res
