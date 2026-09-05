# -*- coding: utf-8 -*-
from typing import List, Tuple

def convert_pymupdf_to_contract_bbox(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    page_width: float,
    page_height: float,
    clip: bool = True
) -> List[float]:
    """
    Converts PyMuPDF bounding box [x0, y0, x1, y1] (left, top, right, bottom)
    into the canonical JSON contract format: [ymin, xmin, ymax, xmax].

    Args:
        x0: Left coordinate
        y0: Top coordinate
        x1: Right coordinate
        y1: Bottom coordinate
        page_width: Page width in points
        page_height: Page height in points
        clip: If True, clips coordinates to page boundaries [0, width] and [0, height].

    Returns:
        Bounding box as [ymin, xmin, ymax, xmax] rounded to 2 decimal places.
    """
    ymin = float(y0)
    xmin = float(x0)
    ymax = float(y1)
    xmax = float(x1)

    if clip:
        xmin = max(0.0, min(xmin, page_width))
        xmax = max(0.0, min(xmax, page_width))
        ymin = max(0.0, min(ymin, page_height))
        ymax = max(0.0, min(ymax, page_height))

    # Ensure min <= max
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    if xmin > xmax:
        xmin, xmax = xmax, xmin

    return [round(ymin, 2), round(xmin, 2), round(ymax, 2), round(xmax, 2)]

def validate_bbox(
    bbox: List[float],
    page_width: float,
    page_height: float,
    tolerance: float = 1.0
) -> Tuple[bool, str]:
    """
    Validates that a bounding box adheres to [ymin, xmin, ymax, xmax] convention
    and resides within the page boundaries.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False, f"Bounding box must be a 4-element list/tuple, got {bbox}"

    ymin, xmin, ymax, xmax = bbox

    if ymin > ymax:
        return False, f"Invalid vertical ordering: ymin ({ymin}) > ymax ({ymax})"

    if xmin > xmax:
        return False, f"Invalid horizontal ordering: xmin ({xmin}) > xmax ({xmax})"

    if ymin < -tolerance or xmin < -tolerance:
        return False, f"Negative coordinates found: ymin={ymin}, xmin={xmin}"

    if xmax > page_width + tolerance:
        return False, f"Coordinate xmax ({xmax}) exceeds page width ({page_width})"

    if ymax > page_height + tolerance:
        return False, f"Coordinate ymax ({ymax}) exceeds page height ({page_height})"

    return True, ""
