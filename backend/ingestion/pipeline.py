# -*- coding: utf-8 -*-
import hashlib
import io
import os
import re
import time
from typing import List, Optional, Tuple

from PIL import Image
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
from .ocr import BaseOCREngine, OCRPageResult, TesseractOCREngine
from .ocr_validator import OCRValidationStatus, validate_ocr_result
from .page_segmenter import classify_document_type
from .preprocessing import preprocess_image_for_ocr
from .quality_assessment import (
    PageQualityAssessment,
    PageQualityGrade,
    assess_page_quality,
)

class DocumentIngestionPipeline:
    """
    Standardized Ingestion Pipeline for PDF Bid and Tender documents.
    Hardened for degraded procurement scans:
    1. PyMuPDF native vector text extraction.
    2. Deterministic physical page optical & quality assessment.
    3. Selective OCR fallback (prefer native on GOOD pages).
    4. Deterministic preprocessing (deskew, contrast normalization, denoising, adaptive thresholding).
    5. Bounded multi-pass OCR for severely degraded pages.
    6. OCR output quality validation & fact gating safety.
    7. Inverse coordinate mapping to canonical PDF page space.
    """

    def __init__(
        self,
        ocr_engine: Optional[BaseOCREngine] = None,
        enable_ocr_fallback: bool = True,
        enable_preprocessing: bool = True,
    ):
        self.ocr_engine = ocr_engine or TesseractOCREngine()
        self.enable_ocr_fallback = enable_ocr_fallback
        self.enable_preprocessing = enable_preprocessing

    def ingest_file(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        bid_id: Optional[str] = None,
        tender_id: Optional[str] = None,
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

        file_size = os.path.getsize(file_path)
        sha256_hash = self._compute_sha256(file_path)
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

                # Step 1: Native PDF Vector Text Extraction
                raw_text = page_obj.get_text()
                raw_blocks = page_obj.get_text("blocks")

                blocks: List[TextBlock] = []
                for b_idx, b in enumerate(raw_blocks):
                    x0, y0, x1, y1, b_text, b_no, b_type = b[:7]
                    contract_bbox = convert_pymupdf_to_contract_bbox(x0, y0, x1, y1, width, height)
                    blocks.append(TextBlock(
                        block_id=f"{doc_id}-p{page_num}-b{b_idx}",
                        page_number=page_num,
                        text=b_text.strip(),
                        raw_text=b_text,
                        bbox=contract_bbox,
                        block_type=int(b_type),
                        confidence=0.98 if b_type == 0 else 0.85,
                    ))

                # Assess baseline extraction quality
                conf_cat, q_score, is_empty, is_low, page_warn = evaluate_page_extraction_quality(
                    raw_text, len(blocks), is_ocr=False
                )

                # Step 2: Deterministic Page Quality Assessment
                # Performance optimization: if native text is rich and clean (>= 120 chars),
                # avoid rendering pixmap entirely to maintain native speed.
                img: Optional[Image.Image] = None
                img_bytes: Optional[bytes] = None

                if len(raw_text.strip()) >= 120 and not is_empty:
                    quality = assess_page_quality(raw_text, len(blocks), width, height, image=None)
                else:
                    # Render page to pixmap for optical inspection
                    pix = page_obj.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        quality = assess_page_quality(raw_text, len(blocks), width, height, image=img, image_bytes=img_bytes)
                    except Exception:
                        quality = PageQualityAssessment(
                            grade=PageQualityGrade.UNKNOWN,
                            dpi=150.0,
                            blur_score=0.0,
                            contrast_score=0.0,
                            mean_intensity=0.0,
                            noise_score=0.0,
                            skew_angle_deg=0.0,
                            native_text_length=len(raw_text.strip()),
                            native_blocks_count=len(blocks),
                            is_scanned=True,
                            reasons=["Failed to decode page pixmap image."],
                        )

                page_method = ExtractionMethod.NATIVE_PDF
                final_text = raw_text
                final_blocks = blocks
                passes_run = 0
                preprocessing_ops: List[str] = []
                val_report_dict: Optional[dict] = None

                # Step 3: Selective OCR Strategy & Multi-Pass Handling
                # Condition: Native text is low/empty OR page optical quality indicates degradation
                needs_ocr = (is_empty or is_low or quality.grade in (PageQualityGrade.DEGRADED, PageQualityGrade.SEVERELY_DEGRADED))

                if needs_ocr and self.enable_ocr_fallback:
                    if self.ocr_engine and self.ocr_engine.is_available():
                        # Ensure pixmap image is rendered
                        if img_bytes is None:
                            pix = page_obj.get_pixmap(dpi=150)
                            img_bytes = pix.tobytes("png")
                            try:
                                img = Image.open(io.BytesIO(img_bytes))
                            except Exception:
                                img = None

                        if img_bytes and img:
                            # -----------------------------------------------------------------
                            # Case A: DEGRADED Page -> Single pass with targeted preprocessing
                            # -----------------------------------------------------------------
                            if quality.grade == PageQualityGrade.DEGRADED:
                                passes_run += 1
                                prep_meta = {}
                                active_bytes = img_bytes

                                if self.enable_preprocessing and (abs(quality.skew_angle_deg) >= 0.5 or quality.contrast_score < 30.0 or quality.noise_score > 16.0):
                                    prep_res = preprocess_image_for_ocr(img, quality)
                                    active_bytes = prep_res.image_bytes
                                    prep_meta = prep_res.to_dict()
                                    preprocessing_ops = prep_res.operations_applied

                                ocr_res = self.ocr_engine.extract_page(
                                    active_bytes, page_num, width, height, preprocessing_meta=prep_meta
                                )
                                val_report_dict = ocr_res.validation_report

                                if ocr_res.success and (len(ocr_res.text.strip()) > len(raw_text.strip()) or is_empty or is_low):
                                    final_text = ocr_res.text
                                    final_blocks = ocr_res.blocks
                                    page_method = ExtractionMethod.OCR
                                    conf_cat, q_score, is_empty, is_low, _ = evaluate_page_extraction_quality(
                                        final_text, len(final_blocks), is_ocr=True, ocr_confidence=ocr_res.confidence
                                    )
                                elif ocr_res.error:
                                    page_warn.append(f"OCR fallback notice: {ocr_res.error}")

                            # -----------------------------------------------------------------
                            # Case B: SEVERELY_DEGRADED Page -> Multi-Pass Strategy (Pass 1 vs 2)
                            # -----------------------------------------------------------------
                            elif quality.grade == PageQualityGrade.SEVERELY_DEGRADED:
                                # PASS 1: Standard OCR (clean image)
                                passes_run += 1
                                p1_meta = {"pass_number": 1, "operations_applied": ["STANDARD_PASS"]}
                                ocr_p1 = self.ocr_engine.extract_page(
                                    img_bytes, page_num, width, height, preprocessing_meta=p1_meta
                                )

                                # PASS 2: Preprocessed OCR (adaptive threshold + contrast + deskew)
                                passes_run += 1
                                prep_res = preprocess_image_for_ocr(img, quality, force_adaptive_threshold=True)
                                p2_meta = prep_res.to_dict()
                                p2_meta["pass_number"] = 2
                                ocr_p2 = self.ocr_engine.extract_page(
                                    prep_res.image_bytes, page_num, width, height, preprocessing_meta=p2_meta
                                )

                                # Compare Pass 1 and Pass 2 deterministically
                                rep1 = ocr_p1.validation_report or {}
                                rep2 = ocr_p2.validation_report or {}
                                score1 = float(rep1.get("composite_score", ocr_p1.confidence if ocr_p1.success else 0.0))
                                score2 = float(rep2.get("composite_score", ocr_p2.confidence if ocr_p2.success else 0.0))

                                if score2 > score1 and ocr_p2.success:
                                    best_ocr = ocr_p2
                                    chosen_pass = 2
                                    preprocessing_ops = prep_res.operations_applied
                                    val_report_dict = rep2
                                    page_warn.append(f"Multi-pass OCR selected Pass 2 (Preprocessed: score {score2:.2f} vs Pass 1: {score1:.2f}).")
                                elif ocr_p1.success:
                                    best_ocr = ocr_p1
                                    chosen_pass = 1
                                    preprocessing_ops = ["STANDARD_PASS"]
                                    val_report_dict = rep1
                                    page_warn.append(f"Multi-pass OCR selected Pass 1 (Standard: score {score1:.2f} vs Pass 2: {score2:.2f}).")
                                else:
                                    # Both passes failed or were rejected by quality validator
                                    best_ocr = None
                                    page_warn.append("All OCR passes rejected by deterministic quality validation (corrupted or unreadable scan).")

                                if best_ocr and best_ocr.success and (len(best_ocr.text.strip()) > len(raw_text.strip()) or is_empty or is_low):
                                    final_text = best_ocr.text
                                    final_blocks = best_ocr.blocks
                                    page_method = ExtractionMethod.OCR
                                    conf_cat, q_score, is_empty, is_low, _ = evaluate_page_extraction_quality(
                                        final_text, len(final_blocks), is_ocr=True, ocr_confidence=best_ocr.confidence
                                    )
                                elif not best_ocr and is_empty:
                                    final_text = ""
                                    final_blocks = []
                                    conf_cat = "LOW"
                                    q_score = 0.0
                            else:
                                # Standard fallback
                                passes_run += 1
                                ocr_res = self.ocr_engine.extract_page(img_bytes, page_num, width, height)
                                if ocr_res.success and len(ocr_res.text.strip()) > len(raw_text.strip()):
                                    final_text = ocr_res.text
                                    final_blocks = ocr_res.blocks
                                    page_method = ExtractionMethod.OCR
                                    val_report_dict = ocr_res.validation_report
                                    conf_cat, q_score, is_empty, is_low, _ = evaluate_page_extraction_quality(
                                        final_text, len(final_blocks), is_ocr=True, ocr_confidence=ocr_res.confidence
                                    )
                    else:
                        page_warn.append(f"Page {page_num} has low/empty text or degraded scan, but OCR engine is unavailable.")

                warnings.extend([f"Page {page_num}: {w}" for w in page_warn])

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
                    quality_grade=quality.grade.value,
                    ocr_passes_count=passes_run,
                    preprocessing_applied=preprocessing_ops,
                    optical_signals=quality.signals,
                    validation_report=val_report_dict,
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
