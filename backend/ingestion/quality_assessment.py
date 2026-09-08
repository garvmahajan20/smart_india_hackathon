# -*- coding: utf-8 -*-
"""
Deterministic Document Quality Assessment.
Evaluates physical page optical metrics (resolution, blur, contrast, brightness, noise, skew)
and text volume to classify page quality into:
- GOOD: Clean digital or sharp scan, high contrast, native text sufficient.
- DEGRADED: Low contrast, faded ink, moderate noise, moderate blur, or low text volume.
- SEVERELY_DEGRADED: Heavy blur, extreme low contrast, heavy noise, significant skew, or unreadable scan.
- UNKNOWN: Missing, empty, or unparseable image data.

CRITICAL INVARIANTS:
1. Deterministic and lightweight (pure numpy + PIL, no ML, no network calls).
2. Never blocks normal extraction for clean pages (PyMuPDF native extraction remains fast).
3. Preserves original page as canonical reference.
"""

from dataclasses import dataclass, field
from enum import Enum
import io
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image


class PageQualityGrade(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    SEVERELY_DEGRADED = "SEVERELY_DEGRADED"
    UNKNOWN = "UNKNOWN"


@dataclass
class PageQualityAssessment:
    """
    Deterministic physical page optical and extraction quality assessment report.
    """
    grade: PageQualityGrade
    dpi: float
    blur_score: float
    contrast_score: float
    mean_intensity: float
    noise_score: float
    skew_angle_deg: float
    native_text_length: int
    native_blocks_count: int
    is_scanned: bool
    reasons: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grade": self.grade.value,
            "dpi": round(self.dpi, 2),
            "blur_score": round(self.blur_score, 2),
            "contrast_score": round(self.contrast_score, 2),
            "mean_intensity": round(self.mean_intensity, 2),
            "noise_score": round(self.noise_score, 2),
            "skew_angle_deg": round(self.skew_angle_deg, 2),
            "native_text_length": self.native_text_length,
            "native_blocks_count": self.native_blocks_count,
            "is_scanned": self.is_scanned,
            "reasons": self.reasons,
            "signals": self.signals,
        }


def compute_laplacian_blur_score(arr_gray: np.ndarray) -> float:
    """
    Computes variance of the discrete 2D Laplacian operator.
    Higher variance indicates sharp, high-frequency edges (crisp text).
    Lower variance indicates blurry or smoothed text.
    """
    if arr_gray.ndim != 2 or arr_gray.shape[0] < 3 or arr_gray.shape[1] < 3:
        return 0.0

    h, w = arr_gray.shape
    padded = np.pad(arr_gray.astype(np.float32), 1, mode="edge")
    lap = (
        padded[0:h, 1:w + 1] + padded[2:h + 2, 1:w + 1] +
        padded[1:h + 1, 0:w] + padded[1:h + 1, 2:w + 2] -
        4.0 * padded[1:h + 1, 1:w + 1]
    )
    return float(np.var(lap))


def compute_contrast_and_intensity(arr_gray: np.ndarray) -> Tuple[float, float, float]:
    """
    Returns (contrast_std, mean_intensity, dynamic_range).
    - contrast_std: Standard deviation of pixel intensities.
    - mean_intensity: Mean brightness (0-255).
    - dynamic_range: 95th percentile minus 5th percentile.
    """
    if arr_gray.size == 0:
        return 0.0, 0.0, 0.0

    mean_val = float(np.mean(arr_gray))
    std_val = float(np.std(arr_gray))
    p5, p95 = np.percentile(arr_gray, [5, 95])
    dyn_range = float(p95 - p5)
    return std_val, mean_val, dyn_range


def compute_noise_score(arr_gray: np.ndarray) -> float:
    """
    Estimates high-frequency noise by comparing pixel values to a 3x3 local uniform blur.
    Returns average absolute residual difference.
    """
    if arr_gray.ndim != 2 or arr_gray.shape[0] < 3 or arr_gray.shape[1] < 3:
        return 0.0

    h, w = arr_gray.shape
    padded = np.pad(arr_gray.astype(np.float32), 1, mode="edge")
    local_mean = (
        padded[0:h, 0:w] + padded[0:h, 1:w + 1] + padded[0:h, 2:w + 2] +
        padded[1:h + 1, 0:w] + padded[1:h + 1, 1:w + 1] + padded[1:h + 1, 2:w + 2] +
        padded[2:h + 2, 0:w] + padded[2:h + 2, 1:w + 1] + padded[2:h + 2, 2:w + 2]
    ) / 9.0

    diff = np.abs(arr_gray.astype(np.float32) - local_mean)
    return float(np.mean(diff))


def estimate_skew_angle_deg(image: Image.Image, max_angle: float = 10.0, step: float = 1.0) -> float:
    """
    Estimates document page skew angle using horizontal projection profile variance.
    When horizontal text lines are aligned, horizontal projection profile variance is maximized.
    """
    try:
        # Downsample for fast, cheap computation (bounded to max width 300px)
        w, h = image.size
        scale = min(1.0, 300.0 / float(w))
        target_size = (max(10, int(w * scale)), max(10, int(h * scale)))
        small = image.resize(target_size, Image.Resampling.NEAREST).convert("L")

        arr = np.array(small)
        # Binary mask of dark pixels (text)
        threshold = int(np.mean(arr) * 0.85)
        binary = (arr < threshold).astype(np.float32)

        base_profile = np.sum(binary, axis=1)
        base_var = float(np.var(base_profile))
        if base_var < 1e-4:
            return 0.0

        best_angle = 0.0
        max_var = base_var

        num_steps = int(2 * max_angle / step) + 1
        angles = np.linspace(-max_angle, max_angle, num_steps)

        for ang in angles:
            if abs(ang) < 0.1:
                continue
            # Rotate binary mask
            rot = small.rotate(float(ang), resample=Image.Resampling.NEAREST, fillcolor=255)
            rot_arr = np.array(rot)
            rot_bin = (rot_arr < threshold).astype(np.float32)
            profile = np.sum(rot_bin, axis=1)
            v = float(np.var(profile))
            if v > max_var:
                max_var = v
                best_angle = float(ang)

        # Require at least 8% variance improvement over base to confirm skew
        if max_var > base_var * 1.08 and abs(best_angle) >= 0.5:
            # Note: rotating image by best_angle aligns it, so skew angle of document is -best_angle
            return float(-best_angle)

        return 0.0
    except Exception:
        return 0.0


def assess_page_quality(
    raw_text: str,
    blocks_count: int,
    page_width: float,
    page_height: float,
    image: Optional[Image.Image] = None,
    image_bytes: Optional[bytes] = None,
) -> PageQualityAssessment:
    """
    Deterministic page quality assessment.
    Takes native extracted text, block counts, and rendered page image (if available).
    Produces a structured PageQualityAssessment with clear quality grade.
    """
    text_clean = raw_text.strip()
    text_len = len(text_clean)
    reasons: List[str] = []

    # 1. Check if rendered image is provided
    img: Optional[Image.Image] = image
    if img is None and image_bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            img = None

    # If no image is available
    if img is None:
        if text_len >= 100:
            return PageQualityAssessment(
                grade=PageQualityGrade.GOOD,
                dpi=72.0,
                blur_score=100.0,
                contrast_score=60.0,
                mean_intensity=240.0,
                noise_score=5.0,
                skew_angle_deg=0.0,
                native_text_length=text_len,
                native_blocks_count=blocks_count,
                is_scanned=False,
                reasons=["Native PDF text extraction is clear and complete."],
                signals={"text_sufficient": True},
            )
        return PageQualityAssessment(
            grade=PageQualityGrade.UNKNOWN,
            dpi=0.0,
            blur_score=0.0,
            contrast_score=0.0,
            mean_intensity=0.0,
            noise_score=0.0,
            skew_angle_deg=0.0,
            native_text_length=text_len,
            native_blocks_count=blocks_count,
            is_scanned=True,
            reasons=["Image unavailable and native text is sparse."],
            signals={"text_sufficient": False},
        )

    # 2. Extract optical metrics from image
    img_gray = img.convert("L")
    arr_gray = np.array(img_gray)
    img_w, img_h = img.size

    dpi_x = (img_w / max(1.0, page_width)) * 72.0
    dpi_y = (img_h / max(1.0, page_height)) * 72.0
    estimated_dpi = (dpi_x + dpi_y) / 2.0

    blur_score = compute_laplacian_blur_score(arr_gray)
    contrast_std, mean_intensity, dyn_range = compute_contrast_and_intensity(arr_gray)
    noise_score = compute_noise_score(arr_gray)
    skew_angle = estimate_skew_angle_deg(img_gray)

    is_scanned = text_len < 40

    signals = {
        "dpi": estimated_dpi,
        "blur_score": blur_score,
        "contrast_std": contrast_std,
        "mean_intensity": mean_intensity,
        "dyn_range": dyn_range,
        "noise_score": noise_score,
        "skew_angle": skew_angle,
        "is_scanned": is_scanned,
    }

    # 3. Decision Logic
    # Case A: Clean digital page with rich native text
    if text_len >= 120 and not is_scanned:
        return PageQualityAssessment(
            grade=PageQualityGrade.GOOD,
            dpi=estimated_dpi,
            blur_score=blur_score,
            contrast_score=contrast_std,
            mean_intensity=mean_intensity,
            noise_score=noise_score,
            skew_angle_deg=skew_angle,
            native_text_length=text_len,
            native_blocks_count=blocks_count,
            is_scanned=False,
            reasons=["Sufficient native vector text; digital PDF layout confirmed."],
            signals=signals,
        )

    # Optical defect detectors
    is_faded = (mean_intensity > 235.0 and contrast_std < 28.0) or dyn_range < 50.0
    is_low_contrast = contrast_std < 32.0 or dyn_range < 65.0
    is_blurry = blur_score < 40.0
    is_severely_blurry = blur_score < 15.0
    is_noisy = noise_score > 16.0
    is_severely_noisy = noise_score > 28.0
    is_skewed = abs(skew_angle) >= 2.0
    is_severely_skewed = abs(skew_angle) >= 4.0
    is_low_res = estimated_dpi < 120.0

    if is_faded:
        reasons.append(f"Faded ink detected (mean brightness {mean_intensity:.1f}, contrast std {contrast_std:.1f}).")
    elif is_low_contrast:
        reasons.append(f"Low contrast document scan (std {contrast_std:.1f}, dynamic range {dyn_range:.1f}).")

    if is_severely_blurry:
        reasons.append(f"Severe optical blur detected (Laplacian variance {blur_score:.1f} < 15).")
    elif is_blurry:
        reasons.append(f"Moderate blur detected (Laplacian variance {blur_score:.1f} < 40).")

    if is_severely_noisy:
        reasons.append(f"Heavy background noise/scanner artifacts detected (noise residual {noise_score:.1f}).")
    elif is_noisy:
        reasons.append(f"Moderate noise detected (noise residual {noise_score:.1f}).")

    if is_severely_skewed:
        reasons.append(f"Significant scan skew detected ({skew_angle:+.1f} degrees).")
    elif is_skewed:
        reasons.append(f"Moderate scan skew detected ({skew_angle:+.1f} degrees).")

    if is_low_res:
        reasons.append(f"Low scan resolution ({estimated_dpi:.1f} DPI < 120 DPI).")

    if is_scanned and text_len == 0:
        reasons.append("Zero native vector text; document is pure raster scan.")

    # Severe degradation criteria
    defect_count = sum([is_faded, is_low_contrast, is_blurry, is_noisy, is_skewed, is_low_res])
    if (
        is_severely_blurry
        or (is_faded and is_blurry)
        or is_severely_noisy
        or is_severely_skewed
        or (is_scanned and defect_count >= 3)
    ):
        grade = PageQualityGrade.SEVERELY_DEGRADED
    elif defect_count >= 1 or is_scanned:
        grade = PageQualityGrade.DEGRADED
    else:
        grade = PageQualityGrade.GOOD

    if not reasons:
        reasons.append("Image resolution and contrast within normal readable parameters.")

    return PageQualityAssessment(
        grade=grade,
        dpi=estimated_dpi,
        blur_score=blur_score,
        contrast_score=contrast_std,
        mean_intensity=mean_intensity,
        noise_score=noise_score,
        skew_angle_deg=skew_angle,
        native_text_length=text_len,
        native_blocks_count=blocks_count,
        is_scanned=is_scanned,
        reasons=reasons,
        signals=signals,
    )
