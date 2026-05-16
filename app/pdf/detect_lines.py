from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectedLines:
    vertical_px: list[int]
    horizontal_px: list[int]


def detect_cut_lines(image: np.ndarray) -> DetectedLines:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    dark = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)[1]

    height, width = dark.shape
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, height // 5)))
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, width // 5), 1))

    vertical_mask = cv2.morphologyEx(dark, cv2.MORPH_OPEN, vertical_kernel)
    horizontal_mask = cv2.morphologyEx(dark, cv2.MORPH_OPEN, horizontal_kernel)

    vertical = _projection_centers(vertical_mask, axis=0, min_strength=max(20, int(height * 0.45)))
    horizontal = _projection_centers(horizontal_mask, axis=1, min_strength=max(20, int(width * 0.45)))

    return DetectedLines(
        vertical_px=_filter_edge_lines(vertical, width),
        horizontal_px=_filter_edge_lines(horizontal, height),
    )


def _projection_centers(mask: np.ndarray, axis: int, min_strength: int) -> list[int]:
    projection = np.count_nonzero(mask, axis=axis)
    candidates = np.where(projection >= min_strength)[0]
    if len(candidates) == 0:
        return []

    groups: list[list[int]] = [[int(candidates[0])]]
    for value in candidates[1:]:
        if int(value) <= groups[-1][-1] + 2:
            groups[-1].append(int(value))
        else:
            groups.append([int(value)])

    return [round(sum(group) / len(group)) for group in groups]


def _filter_edge_lines(lines: list[int], length: int) -> list[int]:
    margin = max(8, int(length * 0.015))
    return [line for line in lines if margin < line < length - margin]
