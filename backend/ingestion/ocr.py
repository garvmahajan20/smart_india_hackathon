# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import io
import shutil
from typing import Any, Dict, List, Optional

from .bbox import convert_pymupdf_to_contract_bbox
from .models import TextBlock
from .ocr_validator import OCRValidationStatus, validate_ocr_result
from .preprocessing import map_ocr_bbox_to_page_coordinates

@dataclass
class OCRPageResult:
    """
    Standardized result from an OCR extraction invocation on a page.
    """
    success: bool
    text: str
    raw_text: str
    blocks: List[TextBlock] = field(default_factory=list)
    confidence: float = 0.0
    error: Optional[str] = None
    engine_name: str = "Tesseract"
    pass_number: int = 1
    preprocessing_applied: List[str] = field(default_factory=list)
    validation_report: Optional[Dict[str, Any]] = None
    quality_status: str = "ACCEPTED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "text": self.text,
            "raw_text": self.raw_text,
            "blocks": [b.to_dict() for b in self.blocks],
            "confidence": round(self.confidence, 4),
            "error": self.error,
            "engine_name": self.engine_name,
            "pass_number": self.pass_number,
            "preprocessing_applied": self.preprocessing_applied,
            "validation_report": self.validation_report,
            "quality_status": self.quality_status,
        }

class BaseOCREngine(ABC):
    """
    Abstract interface for OCR engines. Allows swappable OCR backends
    (Tesseract, AWS Textract, EasyOCR, or Mock for tests).
    """

    @property
    @abstractmethod
    def engine_name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying OCR engine/binary is ready to process."""
        pass

    @abstractmethod
    def extract_page(
        self,
        image_bytes: bytes,
        page_number: int,
        page_width: float,
        page_height: float,
        preprocessing_meta: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> OCRPageResult:
        """
        Executes OCR on an image rendered from a PDF page.
        """
        pass

class TesseractOCREngine(BaseOCREngine):
    """
    Production Tesseract OCR engine using pytesseract.
    Gracefully handles environments where Tesseract is not installed.
    """

    def __init__(self):
        self._checked = False
        self._available = False
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pytesseract
            # Check if tesseract executable is discovered in PATH
            tess_cmd = shutil.which("tesseract")
            if tess_cmd:
                pytesseract.pytesseract.tesseract_cmd = tess_cmd
                self._available = True
            else:
                self._available = False
        except ImportError:
            self._available = False
        self._checked = True

    @property
    def engine_name(self) -> str:
        return "TesseractOCR"

    def is_available(self) -> bool:
        return self._available

    def extract_page(
        self,
        image_bytes: bytes,
        page_number: int,
        page_width: float,
        page_height: float,
        preprocessing_meta: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> OCRPageResult:
        prep_meta = preprocessing_meta or {}
        pass_num = prep_meta.get("pass_number", 1)
        prep_ops = prep_meta.get("operations_applied", [])
        skew_deg = prep_meta.get("skew_angle_deg", 0.0)
        scale_fact = prep_meta.get("scale_factor", 1.0)

        if not self.is_available():
            return OCRPageResult(
                success=False,
                text="",
                raw_text="",
                blocks=[],
                confidence=0.0,
                error="Tesseract is not installed or available in current environment.",
                engine_name=self.engine_name,
                pass_number=pass_num,
                preprocessing_applied=prep_ops,
                quality_status="FAILED",
            )

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
            img_w, img_h = image.size

            # Extract detailed block and bounding box data using image_to_data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            blocks: List[TextBlock] = []
            full_text_lines: List[str] = []
            confidences: List[float] = []

            # Group words into blocks
            current_block_num = -1
            current_block_words: List[str] = []
            current_block_coords: Optional[List[float]] = None

            n_boxes = len(data["level"])

            for i in range(n_boxes):
                text_word = data["text"][i].strip()
                conf = float(data["conf"][i])
                block_num = data["block_num"][i]

                if not text_word or conf < 0:
                    continue

                confidences.append(conf / 100.0)
                px = float(data["left"][i])
                py = float(data["top"][i])
                pw = float(data["width"][i])
                ph = float(data["height"][i])

                if block_num != current_block_num and current_block_words:
                    block_text = " ".join(current_block_words)
                    full_text_lines.append(block_text)

                    # Map coordinates back to canonical PDF page space
                    b_box = map_ocr_bbox_to_page_coordinates(
                        current_block_coords,
                        image.size,
                        (page_width, page_height),
                        skew_angle_applied=skew_deg,
                        scale_factor=scale_fact,
                    )
                    block_conf = sum(confidences[-len(current_block_words):]) / max(1, len(current_block_words))

                    blocks.append(TextBlock(
                        block_id=f"ocr-p{page_number}-b{len(blocks)}",
                        page_number=page_number,
                        text=block_text,
                        raw_text=block_text,
                        bbox=b_box,
                        confidence=block_conf,
                    ))
                    current_block_words = []

                current_block_num = block_num
                current_block_words.append(text_word)
                if current_block_coords is None:
                    current_block_coords = [px, py, px + pw, py + ph]
                else:
                    current_block_coords[0] = min(current_block_coords[0], px)
                    current_block_coords[1] = min(current_block_coords[1], py)
                    current_block_coords[2] = max(current_block_coords[2], px + pw)
                    current_block_coords[3] = max(current_block_coords[3], py + ph)

            if current_block_words and current_block_coords:
                block_text = " ".join(current_block_words)
                full_text_lines.append(block_text)

                b_box = map_ocr_bbox_to_page_coordinates(
                    current_block_coords,
                    image.size,
                    (page_width, page_height),
                    skew_angle_applied=skew_deg,
                    scale_factor=scale_fact,
                )
                blocks.append(TextBlock(
                    block_id=f"ocr-p{page_number}-b{len(blocks)}",
                    page_number=page_number,
                    text=block_text,
                    raw_text=block_text,
                    bbox=b_box,
                    confidence=0.85,
                ))

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.85
            extracted_text = "\n".join(full_text_lines)

            # Deterministic OCR Output Validation
            val_report = validate_ocr_result(extracted_text, blocks, avg_conf)

            if val_report.status == OCRValidationStatus.FAILED:
                # Discard garbage OCR
                return OCRPageResult(
                    success=False,
                    text="",
                    raw_text="",
                    blocks=[],
                    confidence=val_report.confidence,
                    error=f"OCR quality validation failed: {'; '.join(val_report.reasons)}",
                    engine_name=self.engine_name,
                    pass_number=pass_num,
                    preprocessing_applied=prep_ops,
                    validation_report=val_report.to_dict(),
                    quality_status=val_report.status.value,
                )

            return OCRPageResult(
                success=True,
                text=extracted_text,
                raw_text=extracted_text,
                blocks=blocks,
                confidence=avg_conf,
                error=None,
                engine_name=self.engine_name,
                pass_number=pass_num,
                preprocessing_applied=prep_ops,
                validation_report=val_report.to_dict(),
                quality_status=val_report.status.value,
            )

        except Exception as e:
            return OCRPageResult(
                success=False,
                text="",
                raw_text="",
                blocks=[],
                confidence=0.0,
                error=f"OCR execution failed: {str(e)}",
                engine_name=self.engine_name,
                pass_number=pass_num,
                preprocessing_applied=prep_ops,
                quality_status="FAILED",
            )

class MockOCREngine(BaseOCREngine):
    """
    Mock OCR Engine for controlled unit testing of fallback, multi-pass,
    and hybrid pipelines without external binary dependencies.
    """

    def __init__(
        self,
        simulated_text: str = "Simulated OCR Extracted Text",
        available: bool = True,
        confidence: float = 0.92,
        pass2_simulated_text: Optional[str] = None,
        force_failed_validation: bool = False,
    ):
        self.simulated_text = simulated_text
        self._available = available
        self.confidence = confidence
        self.pass2_simulated_text = pass2_simulated_text
        self.force_failed_validation = force_failed_validation

    @property
    def engine_name(self) -> str:
        return "MockOCREngine"

    def is_available(self) -> bool:
        return self._available

    def extract_page(
        self,
        image_bytes: bytes,
        page_number: int,
        page_width: float,
        page_height: float,
        preprocessing_meta: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> OCRPageResult:
        prep_meta = preprocessing_meta or {}
        pass_num = prep_meta.get("pass_number", 1)
        prep_ops = prep_meta.get("operations_applied", [])
        skew_deg = prep_meta.get("skew_angle_deg", 0.0)
        scale_fact = prep_meta.get("scale_factor", 1.0)

        if not self.is_available():
            return OCRPageResult(
                success=False,
                text="",
                raw_text="",
                blocks=[],
                confidence=0.0,
                error="Mock OCR engine marked unavailable for test.",
                engine_name=self.engine_name,
                pass_number=pass_num,
                preprocessing_applied=prep_ops,
                quality_status="FAILED",
            )

        # Multi-pass simulation: if pass 2 and specific text configured, use it
        chosen_text = self.simulated_text
        if pass_num == 2 and self.pass2_simulated_text is not None:
            chosen_text = self.pass2_simulated_text

        if self.force_failed_validation:
            chosen_text = "^^^~===+++!!!???;;;..."

        # Compute bounding box and transform with coordinate mapping
        pixel_box = [50.0 * scale_fact, 50.0 * scale_fact, (page_width - 50.0) * scale_fact, 150.0 * scale_fact]
        bbox = map_ocr_bbox_to_page_coordinates(
            pixel_box,
            (int(page_width * scale_fact), int(page_height * scale_fact)),
            (page_width, page_height),
            skew_angle_applied=skew_deg,
            scale_factor=scale_fact,
        )

        block = TextBlock(
            block_id=f"mock-ocr-p{page_number}-b0",
            page_number=page_number,
            text=chosen_text,
            raw_text=chosen_text,
            bbox=bbox,
            confidence=self.confidence,
        )

        val_report = validate_ocr_result(chosen_text, [block], self.confidence)

        if val_report.status == OCRValidationStatus.FAILED or self.force_failed_validation:
            return OCRPageResult(
                success=False,
                text="",
                raw_text="",
                blocks=[],
                confidence=val_report.confidence,
                error=f"Mock OCR validation failed: {'; '.join(val_report.reasons)}",
                engine_name=self.engine_name,
                pass_number=pass_num,
                preprocessing_applied=prep_ops,
                validation_report=val_report.to_dict(),
                quality_status="FAILED",
            )

        return OCRPageResult(
            success=True,
            text=chosen_text,
            raw_text=chosen_text,
            blocks=[block],
            confidence=self.confidence,
            error=None,
            engine_name=self.engine_name,
            pass_number=pass_num,
            preprocessing_applied=prep_ops,
            validation_report=val_report.to_dict(),
            quality_status=val_report.status.value,
        )
