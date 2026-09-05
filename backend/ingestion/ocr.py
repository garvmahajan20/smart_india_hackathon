# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import io
import shutil
from typing import Any, Dict, List, Optional

from .bbox import convert_pymupdf_to_contract_bbox
from .models import TextBlock

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
        page_height: float
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
        page_height: float
    ) -> OCRPageResult:
        if not self.is_available():
            return OCRPageResult(
                success=False,
                text="",
                raw_text="",
                blocks=[],
                confidence=0.0,
                error="Tesseract is not installed or available in current environment.",
                engine_name=self.engine_name,
            )

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
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
            img_w, img_h = image.size
            scale_x = page_width / img_w if img_w > 0 else 1.0
            scale_y = page_height / img_h if img_h > 0 else 1.0

            for i in range(n_boxes):
                text_word = data["text"][i].strip()
                conf = float(data["conf"][i])
                block_num = data["block_num"][i]

                if not text_word or conf < 0:
                    continue

                confidences.append(conf / 100.0)
                x = data["left"][i] * scale_x
                y = data["top"][i] * scale_y
                w = data["width"][i] * scale_x
                h = data["height"][i] * scale_y

                if block_num != current_block_num and current_block_words:
                    block_text = " ".join(current_block_words)
                    full_text_lines.append(block_text)
                    b_box = convert_pymupdf_to_contract_bbox(
                        current_block_coords[0], current_block_coords[1],
                        current_block_coords[2], current_block_coords[3],
                        page_width, page_height
                    )
                    blocks.append(TextBlock(
                        block_id=f"ocr-p{page_number}-b{len(blocks)}",
                        page_number=page_number,
                        text=block_text,
                        raw_text=block_text,
                        bbox=b_box,
                        confidence=sum(confidences[-len(current_block_words):]) / len(current_block_words)
                    ))
                    current_block_words = []

                current_block_num = block_num
                current_block_words.append(text_word)
                if current_block_coords is None:
                    current_block_coords = [x, y, x + w, y + h]
                else:
                    current_block_coords[0] = min(current_block_coords[0], x)
                    current_block_coords[1] = min(current_block_coords[1], y)
                    current_block_coords[2] = max(current_block_coords[2], x + w)
                    current_block_coords[3] = max(current_block_coords[3], y + h)

            if current_block_words and current_block_coords:
                block_text = " ".join(current_block_words)
                full_text_lines.append(block_text)
                b_box = convert_pymupdf_to_contract_bbox(
                    current_block_coords[0], current_block_coords[1],
                    current_block_coords[2], current_block_coords[3],
                    page_width, page_height
                )
                blocks.append(TextBlock(
                    block_id=f"ocr-p{page_number}-b{len(blocks)}",
                    page_number=page_number,
                    text=block_text,
                    raw_text=block_text,
                    bbox=b_box,
                    confidence=0.85
                ))

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.85
            extracted_text = "\n".join(full_text_lines)

            return OCRPageResult(
                success=True,
                text=extracted_text,
                raw_text=extracted_text,
                blocks=blocks,
                confidence=avg_conf,
                error=None,
                engine_name=self.engine_name,
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
            )

class MockOCREngine(BaseOCREngine):
    """
    Mock OCR Engine for controlled unit testing of fallback and hybrid pipelines
    without requiring external binaries or environment dependencies.
    """

    def __init__(self, simulated_text: str = "Simulated OCR Extracted Text", available: bool = True):
        self.simulated_text = simulated_text
        self._available = available

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
        page_height: float
    ) -> OCRPageResult:
        if not self.is_available():
            return OCRPageResult(
                success=False,
                text="",
                raw_text="",
                blocks=[],
                confidence=0.0,
                error="Mock OCR engine marked unavailable for test.",
                engine_name=self.engine_name,
            )

        bbox = convert_pymupdf_to_contract_bbox(50.0, 50.0, page_width - 50.0, 150.0, page_width, page_height)
        block = TextBlock(
            block_id=f"mock-ocr-p{page_number}-b0",
            page_number=page_number,
            text=self.simulated_text,
            raw_text=self.simulated_text,
            bbox=bbox,
            confidence=0.92
        )
        return OCRPageResult(
            success=True,
            text=self.simulated_text,
            raw_text=self.simulated_text,
            blocks=[block],
            confidence=0.92,
            error=None,
            engine_name=self.engine_name,
        )
