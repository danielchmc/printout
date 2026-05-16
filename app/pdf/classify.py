from __future__ import annotations

from app.pdf.constants import A4_HEIGHT_PT, A4_WIDTH_PT


def classify_region(width_pt: float, height_pt: float) -> str:
    if _matches_size(width_pt, height_pt, A4_WIDTH_PT, A4_HEIGHT_PT):
        return "A4"
    if _matches_size(width_pt, height_pt, A4_HEIGHT_PT / 2, A4_WIDTH_PT):
        return "A5"
    if _matches_size(width_pt, height_pt, A4_WIDTH_PT / 2, A4_HEIGHT_PT / 2):
        return "A6"
    if _matches_size(width_pt, height_pt, A4_HEIGHT_PT / 4, A4_WIDTH_PT / 2):
        return "A7"
    return "custom"


def _matches_size(width: float, height: float, expected_width: float, expected_height: float) -> bool:
    tolerance = 8
    direct = abs(width - expected_width) <= tolerance and abs(height - expected_height) <= tolerance
    rotated = abs(width - expected_height) <= tolerance and abs(height - expected_width) <= tolerance
    return direct or rotated
