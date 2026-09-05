# -*- coding: utf-8 -*-
import hashlib
import os
import re
from typing import List, Optional

import pymupdf

from .bbox import convert_pymupdf_to_contract_bbox
from .confidence import evaluate_page_extraction_quality
from .models import (
    DocumentMetadata,
    DocumentType,
    ExtractedPage,
    ExtractionMethod,
    ExtractionResult,
    TextBlock,
)
from .ocr import BaseOCREngine, TesseractOCREngine
from .page_segmenter import classify_document_type

class DocumentIngestionPipeline:
    """
    Standardized Ingestion Pipeline for PDF Bid and Tender documents.
    Coordinates PyMuPDF native extraction, bounding box canonicalization,
    quality heuristic assessment, and selective OCR fallback.
    """

    def __init__(self, ocr_engine: Optional[BaseOCREngine] = None, enable_ocr_fallback: bool = True):
        self.ocr_engine = ocr_engine or TesseractOCREngine()
        self.enable_ocr_fallback = enable_ocr_fallback

    def ingest_file(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        bid_id: Optional[str] = None,
        tender_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Ingests a PDF document from disk and produces a structured ExtractionResult.
        """
        filename = os.path.basename(file_path)
        doc_id = document_id or f"DOC-{os.path.splitext(filename)[0]}"

        # Infer bid_id or tender_id from filename if not explicitly provided
        inferred_bid_id = bid_id
        inferred_tender_id = tender_id
        if not inferred_bid_id and re.search(r"BID-\d+", filename, re.IGNORECASE):
            match = re.search(r"BID-\d+", filename, re.IGNORECASE)
            if match:
                inferred_bid_id = match.group(0).upper()
        if not inferred_tender_id and re.search(r"TENDER-\d+", filename, re.IGNORECASE):
            match = re.search(r"TENDER-\d+", filename, re.IGNORECASE)
            if match:
                inferred_tender_id = match.group(0).upper()

        # Handle non-existent file gracefully
        if not os.path.exists(file_path):
            empty_meta = DocumentMetadata(
                document_id=doc_id,
                filename=filename,
                file_path=file_path,
                file_size_bytes=0,
                sha256="",
                page_count=0,
                document_type=DocumentType.UNKNOWN,
                bid_id=inferred_bid_id,
                tender_id=inferred_tender_id,
            )
            return ExtractionResult(
                document_id=doc_id,
                metadata=empty_meta,
                pages=[],
                overall_method=ExtractionMethod.FAILED,
                overall_confidence="LOW",
                errors=[f"File does not exist: '{file_path}'"],
            )

        # File size and SHA-256
        file_size = os.path.getsize(file_path)
        sha256_hash = self._compute_sha256(file_path)

        # Document type inference
        inferred_type = document_type or classify_document_type(filename, file_path)

        metadata = DocumentMetadata(
            document_id=doc_id,
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size,
            sha256=sha256_hash,
            page_count=0,
            document_type=inferred_type,
            bid_id=inferred_bid_id,
            tender_id=inferred_tender_id,
        )

        pages: List[ExtractedPage] = []
        errors: List[str] = []
        warnings: List[str] = []

        try:
            doc = pymupdf.open(file_path)
            metadata.page_count = len(doc)

            for page_idx in range(len(doc)):
                page_num = page_idx + 1
                page_obj = doc[page_idx]
                width = float(page_obj.rect.width)
                height = float(page_obj.rect.height)

                raw_text = page_obj.get_text()
                raw_blocks = page_obj.get_text("blocks")

                blocks: List[TextBlock] = []
                for b_idx, b in enumerate(raw_blocks):
                    # b: (x0, y0, x1, y1, text, block_no, block_type)
                    x0, y0, x1, y1, b_text, b_no, b_type = b[:7]
                    contract_bbox = convert_pymupdf_to_contract_bbox(x0, y0, x1, y1, width, height)

                    blocks.append(TextBlock(
                        block_id=f"{doc_id}-p{page_num}-b{b_idx}",
                        page_number=page_num,
                        text=b_text.strip(),
                        raw_text=b_text,
                        bbox=contract_bbox,
                        block_type=int(b_type),
                        confidence=0.98 if b_type == 0 else 0.85
                    ))

                # Assess extraction quality
                conf_cat, q_score, is_empty, is_low, page_warn = evaluate_page_extraction_quality(
                    raw_text, len(blocks), is_ocr=False
                )
                warnings.extend([f"Page {page_num}: {w}" for w in page_warn])

                page_method = ExtractionMethod.NATIVE_PDF
                final_text = raw_text
                final_blocks = blocks

                # Check if OCR fallback should be triggered
                if (is_empty or is_low) and self.enable_ocr_fallback:
                    if self.ocr_engine and self.ocr_engine.is_available():
                        # Render page to pixmap image
                        pix = page_obj.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        ocr_res = self.ocr_engine.extract_page(img_bytes, page_num, width, height)

                        if ocr_res.success and len(ocr_res.text.strip()) > len(raw_text.strip()):
                            final_text = ocr_res.text
                            final_blocks = ocr_res.blocks
                            page_method = ExtractionMethod.OCR
                            conf_cat, q_score, is_empty, is_low, _ = evaluate_page_extraction_quality(
                                final_text, len(final_blocks), is_ocr=True, ocr_confidence=ocr_res.confidence
                            )
                        elif ocr_res.error:
                            warnings.append(f"Page {page_num} OCR fallback failed: {ocr_res.error}")
                    else:
                        warnings.append(f"Page {page_num} has low/empty text, but OCR engine is unavailable.")

                pages.append(ExtractedPage(
                    page_number=page_num,
                    width=width,
                    height=height,
                    text=final_text.strip(),
                    raw_text=final_text,
                    blocks=final_blocks,
                    extraction_method=page_method,
                    extraction_confidence=conf_cat,
                    quality_score=q_score,
                    is_empty=is_empty,
                    is_low_text=is_low,
                    warnings=page_warn,
                ))

            doc.close()

        except Exception as e:
            errors.append(f"Failed to process PDF '{file_path}': {str(e)}")
            return ExtractionResult(
                document_id=doc_id,
                metadata=metadata,
                pages=[],
                overall_method=ExtractionMethod.FAILED,
                overall_confidence="LOW",
                errors=errors,
                warnings=warnings,
            )

        # Determine overall method
        methods = {p.extraction_method for p in pages}
        if ExtractionMethod.OCR in methods and ExtractionMethod.NATIVE_PDF in methods:
            overall_method = ExtractionMethod.HYBRID
        elif ExtractionMethod.OCR in methods:
            overall_method = ExtractionMethod.OCR
        else:
            overall_method = ExtractionMethod.NATIVE_PDF

        # Overall confidence
        if any(p.extraction_confidence == "LOW" for p in pages):
            overall_conf = "LOW"
        elif any(p.extraction_confidence == "MEDIUM" for p in pages):
            overall_conf = "MEDIUM"
        else:
            overall_conf = "HIGH"

        total_chars = sum(len(p.text) for p in pages)
        total_blocks = sum(len(p.blocks) for p in pages)

        return ExtractionResult(
            document_id=doc_id,
            metadata=metadata,
            pages=pages,
            overall_method=overall_method,
            overall_confidence=overall_conf,
            total_text_length=total_chars,
            total_blocks=total_blocks,
            errors=errors,
            warnings=warnings,
        )

    def _compute_sha256(self, file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
