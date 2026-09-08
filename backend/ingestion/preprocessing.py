# -*- coding: utf-8 -*-
"""
Deterministic Preprocessing Pipeline for Degraded Procurement Documents.
Provides conservative image enhancement operations specifically tuned for:
- Faded scans / faint ink
- Low contrast
- Salt-and-pepper scan noise
- Small document skew / rotation
- Low resolution

CRITICAL GOVERNANCE INVARIANTS:
1. Preprocessed images are OCR inputs only. The original page remains the canonical source.
2. Coordinates produced in preprocessed space are mapped deterministically back to canonical
   PDF page coordinates [ymin, xmin, ymax, xmax].
3. Never fabricates [0,0,0,0] bounding boxes for physical text evidence.
4. Deterministic and fast (no non-deterministic randomness).
"""

from dataclasses import dataclass, field
import io
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

from .bbox import convert_pymupdf_to_contract_bbox
from .quality_assessment import PageQualityAssessment, PageQualityGrade


@dataclass
class PreprocessedImageResult:
    """
    Result container holding the enhanced image for OCR and transformation metadata.
    """
    image_bytes: bytes
    processed_image: Image.Image
    operations_applied: List[str] = field(default_factory=list)
    skew_angle_deg: float = 0.0
    scale_factor: float = 1.0
    original_size: Tuple[int, int] = (0, 0)
    processed_size: Tuple[int, int] = (0, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operations_applied": self.operations_applied,
            "skew_angle_deg": round(self.skew_angle_deg, 2),
            "scale_factor": round(self.scale_factor, 3),
            "original_size": list(self.original_size),
            "processed_size": list(self.processed_size),
        }


def normalize_contrast(image: Image.Image, p_low: float = 2.0, p_high: float = 98.0) -> Image.Image:
    """
    Performs percentile-based histogram stretching.
    Maps p_low percentile to 0 and p_high percentile to 255.
    Recovers faint text without blowing out background.
    """
    img_gray = image.convert("L")
    arr = np.array(img_gray, dtype=np.float32)
    v_min, v_max = np.percentile(arr, [p_low, p_high])
    if v_max <= v_min + 1e-4:
        v_min, v_max = float(arr.min()), float(arr.max())
    if v_max <= v_min + 1e-4:
        return image

    stretched = np.clip((arr - v_min) / (v_max - v_min) * 255.0, 0.0, 255.0).astype(np.uint8)
    return Image.fromarray(stretched, mode="L")


def denoise_image(image: Image.Image) -> Image.Image:
    """
    Applies a 3x3 median filter to eliminate salt-and-pepper scanner noise
    while preserving edge sharpness of text strokes and numbers.
    """
    return image.filter(ImageFilter.MedianFilter(size=3))


def adaptive_threshold_sauvola(image: Image.Image, window_size: int = 15, k: float = 0.2) -> Image.Image:
    """
    Deterministic adaptive binarization based on local mean and standard deviation.
    Specifically effective for faded procurement documents with non-uniform lighting.
    Threshold: T = mean * (1 + k * (std / 128.0 - 1))
    """
    img_gray = image.convert("L")
    arr = np.array(img_gray, dtype=np.float32)
    h, w = arr.shape

    # Fast local mean using uniform box filter
    padded = np.pad(arr, window_size // 2, mode="edge")
    # Use PIL BoxBlur for fast C-level box filtering
    blur_img = Image.fromarray(padded.astype(np.uint8)).filter(ImageFilter.BoxBlur(window_size // 2))
    blur_arr = np.array(blur_img, dtype=np.float32)[
        window_size // 2 : window_size // 2 + h,
        window_size // 2 : window_size // 2 + w
    ]

    # Global std approximation for stability
    global_std = float(np.std(arr))
    threshold = blur_arr * (1.0 + k * (global_std / 128.0 - 1.0))

    binary = np.where(arr < threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(binary, mode="L")


def deskew_image(image: Image.Image, skew_angle_deg: float) -> Tuple[Image.Image, float]:
    """
    Rotates image to correct scan skew.
    Rotates by -skew_angle_deg around center with bilinear interpolation.
    Fills outer boundaries with white background (255).
    """
    if abs(skew_angle_deg) < 0.5:
        return image, 0.0

    # Rotate counter-clockwise by -skew_angle_deg
    corrected = image.rotate(-skew_angle_deg, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=255)
    return corrected, float(-skew_angle_deg)


def preprocess_image_for_ocr(
    image: Image.Image,
    assessment: PageQualityAssessment,
    force_adaptive_threshold: bool = False,
) -> PreprocessedImageResult:
    """
    Selectively and deterministically applies image preprocessing based on assessed defects.
    """
    orig_w, orig_h = image.size
    current_img = image.convert("L")
    applied: List[str] = []
    skew_deg = 0.0
    scale = 1.0

    # 1. Deskew if skew angle exceeds threshold (0.5 degrees)
    if abs(assessment.skew_angle_deg) >= 0.5:
        current_img, skew_deg = deskew_image(current_img, assessment.skew_angle_deg)
        applied.append(f"DESKEW({assessment.skew_angle_deg:+.1f}deg)")

    # 2. Upscaling if resolution is low (< 130 DPI)
    if assessment.dpi < 130.0 and orig_w < 1800 and orig_h < 2400:
        scale = min(2.0, 1800.0 / float(orig_w))
        if scale > 1.1:
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            current_img = current_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            applied.append(f"RESCALE({scale:.2f}x)")

    # 3. Denoising if noise is elevated
    if assessment.noise_score > 8.0:
        current_img = denoise_image(current_img)
        applied.append("MEDIAN_DENOISE")

    # 4. Contrast normalization for faded or low-contrast scans
    mean_val = assessment.mean_intensity
    contrast_std = assessment.contrast_score
    is_faded = (mean_val > 230.0 and contrast_std < 32.0) or contrast_std < 28.0

    if is_faded or force_adaptive_threshold:
        current_img = normalize_contrast(current_img)
        applied.append("CONTRAST_STRETCH")

        # For severely degraded or faded pages, apply adaptive binarization
        if assessment.grade == PageQualityGrade.SEVERELY_DEGRADED or force_adaptive_threshold:
            current_img = adaptive_threshold_sauvola(current_img)
            applied.append("ADAPTIVE_BINARIZE")

    # Convert to PNG bytes
    buf = io.BytesIO()
    current_img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    return PreprocessedImageResult(
        image_bytes=img_bytes,
        processed_image=current_img,
        operations_applied=applied,
        skew_angle_deg=skew_deg,
        scale_factor=scale,
        original_size=(orig_w, orig_h),
        processed_size=current_img.size,
    )


def map_ocr_bbox_to_page_coordinates(
    ocr_pixel_bbox: List[float],  # [x0, y0, x1, y1] in processed image pixel space
    processed_img_size: Tuple[int, int],
    page_size_pts: Tuple[float, float],
    skew_angle_applied: float = 0.0,
    scale_factor: float = 1.0,
) -> List[float]:
    """
    Deterministically transforms a bounding box from processed OCR image space back
    into canonical PDF page coordinate space [ymin, xmin, ymax, xmax].

    Args:
        ocr_pixel_bbox: [x0, y0, x1, y1] in processed image pixel coordinates.
        processed_img_size: (width, height) of the processed image.
        page_size_pts: (page_width, page_height) in PDF points.
        skew_angle_applied: Rotation angle in degrees that was applied to the image (e.g. -theta).
        scale_factor: Scaling multiplier applied during preprocessing (e.g. 1.5x).

    Returns:
        Bounding box [ymin, xmin, ymax, xmax] in PDF points, clamped to page boundaries.
    """
    pw_img, ph_img = processed_img_size
    page_w, page_h = page_size_pts

    x0, y0, x1, y1 = [float(v) for v in ocr_pixel_bbox[:4]]

    # 1. Reverse rotation if image was rotated
    if abs(skew_angle_applied) >= 0.01:
        cx = pw_img / 2.0
        cy = ph_img / 2.0
        # Invert the rotation: angle applied was skew_angle_applied (which was -skew_deg)
        # To invert, we apply -skew_angle_applied in the screen coordinate system
        rad = math.radians(skew_angle_applied)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        corners = [
            (x0, y0),
            (x1, y0),
            (x1, y1),
            (x0, y1),
        ]
        mapped_xs: List[float] = []
        mapped_ys: List[float] = []

        for px, py in corners:
            # Screen coordinate rotation inverse
            rx = cx + (px - cx) * cos_a - (py - cy) * sin_a
            ry = cy + (px - cx) * sin_a + (py - cy) * cos_a
            mapped_xs.append(rx)
            mapped_ys.append(ry)

        x0 = min(mapped_xs)
        x1 = max(mapped_xs)
        y0 = min(mapped_ys)
        y1 = max(mapped_ys)

    # 2. Reverse scaling
    if scale_factor > 0 and abs(scale_factor - 1.0) >= 0.01:
        x0 /= scale_factor
        x1 /= scale_factor
        y0 /= scale_factor
        y1 /= scale_factor
        # Original pixel dimensions before scaling
        orig_img_w = pw_img / scale_factor
        orig_img_h = ph_img / scale_factor
    else:
        orig_img_w = float(pw_img)
        orig_img_h = float(ph_img)

    # 3. Map to PDF page points
    scale_x = page_w / orig_img_w if orig_img_w > 0 else 1.0
    scale_y = page_h / orig_img_h if orig_img_h > 0 else 1.0

    pts_x0 = x0 * scale_x
    pts_x1 = x1 * scale_x
    pts_y0 = y0 * scale_y
    pts_y1 = y1 * scale_y

    # 4. Convert to canonical contract bbox [ymin, xmin, ymax, xmax]
    return convert_pymupdf_to_contract_bbox(pts_x0, pts_y0, pts_x1, pts_y1, page_w, page_h)
