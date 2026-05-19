from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import fitz
import numpy as np

from app.models import Confidence, DetectedRegion, RegionRect
from app.pdf.classify import classify_region
from app.pdf.detect_lines import detect_cut_lines
from app.pdf.render import render_page_to_rgb


def analyze_pdf(path: Path, file_id: str, dpi: int = 200) -> tuple[int, list[DetectedRegion]]:
    regions: list[DetectedRegion] = []
    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            image = render_page_to_rgb(page, dpi=dpi)
            lines = detect_cut_lines(image)
            page_regions = build_regions(page, image, lines.vertical_px, lines.horizontal_px)
            for rect, occupancy_ratio in page_regions:
                width_pt = rect.x1 - rect.x0
                height_pt = rect.y1 - rect.y0
                label_type = classify_region(width_pt, height_pt)
                confidence = score_confidence(label_type, occupancy_ratio, lines_found=bool(lines.vertical_px or lines.horizontal_px))
                regions.append(
                    DetectedRegion(
                        id=uuid.uuid4().hex,
                        source_file=path.name,
                        source_path=str(path),
                        page_index=page_index,
                        rect=rect,
                        width_pt=width_pt,
                        height_pt=height_pt,
                        label_type=label_type,
                        occupied=occupancy_ratio >= 0.0025,
                        confidence=confidence,
                        occupancy_ratio=occupancy_ratio,
                    )
                )
        return document.page_count, regions


def build_regions(
    page: fitz.Page,
    image: np.ndarray,
    vertical_lines_px: list[int],
    horizontal_lines_px: list[int],
) -> list[tuple[RegionRect, float]]:
    if not vertical_lines_px and not horizontal_lines_px:
        fallback = build_fallback_regions(page, image)
        if fallback:
            return fallback

    height_px, width_px = image.shape[:2]
    x_edges = [0, *vertical_lines_px, width_px]
    y_edges = [0, *horizontal_lines_px, height_px]

    regions: list[tuple[RegionRect, float]] = []
    for y0_px, y1_px in zip(y_edges, y_edges[1:]):
        for x0_px, x1_px in zip(x_edges, x_edges[1:]):
            if x1_px - x0_px < 20 or y1_px - y0_px < 20:
                continue
            rect = RegionRect(
                x0=page.rect.x0 + (x0_px / width_px) * page.rect.width,
                y0=page.rect.y0 + (y0_px / height_px) * page.rect.height,
                x1=page.rect.x0 + (x1_px / width_px) * page.rect.width,
                y1=page.rect.y0 + (y1_px / height_px) * page.rect.height,
            )
            crop = image[y0_px:y1_px, x0_px:x1_px]
            regions.append((rect, occupancy_ratio(crop)))

    if not regions:
        whole_page = RegionRect(x0=page.rect.x0, y0=page.rect.y0, x1=page.rect.x1, y1=page.rect.y1)
        regions.append((whole_page, occupancy_ratio(image)))

    return regions


def build_fallback_regions(page: fitz.Page, image: np.ndarray) -> list[tuple[RegionRect, float]]:
    content_bbox = content_bounds_px(image)
    if content_bbox is None:
        return []

    height_px, width_px = image.shape[:2]
    x0, y0, x1, y1 = content_bbox
    tolerance_px = max(8, int(min(width_px, height_px) * 0.012))

    candidates: list[tuple[int, int, int, int, int, int, int, int]] = []
    for columns, rows in fallback_grids(page):
        cell_width = width_px / columns
        cell_height = height_px / rows
        for row in range(rows):
            for column in range(columns):
                cx0 = round(column * cell_width)
                cy0 = round(row * cell_height)
                cx1 = round((column + 1) * cell_width)
                cy1 = round((row + 1) * cell_height)
                if (
                    x0 >= cx0 - tolerance_px
                    and y0 >= cy0 - tolerance_px
                    and x1 <= cx1 + tolerance_px
                    and y1 <= cy1 + tolerance_px
                ):
                    candidates.append((cx0, cy0, cx1, cy1, columns, rows, column, row))

    if not candidates:
        return []

    candidates.sort(key=lambda item: (item[2] - item[0]) * (item[3] - item[1]))
    cx0, cy0, cx1, cy1, columns, rows, column, row = candidates[0]
    rect = RegionRect(
        x0=page.rect.x0 + (column / columns) * page.rect.width,
        y0=page.rect.y0 + (row / rows) * page.rect.height,
        x1=page.rect.x0 + ((column + 1) / columns) * page.rect.width,
        y1=page.rect.y0 + ((row + 1) / rows) * page.rect.height,
    )
    if classify_region(rect.width, rect.height) == "A4":
        multi_cell_regions = build_multi_cell_fallback_regions(page, image, width_px, height_px)
        if len(multi_cell_regions) > 1:
            return multi_cell_regions

    if classify_region(rect.width, rect.height) == "custom":
        rect, cx0, cx1, cy0, cy1 = trim_custom_region_to_content_bounds(
            page,
            rect,
            x0,
            x1,
            y0,
            y1,
            width_px,
            height_px,
            cx0,
            cx1,
            cy0,
            cy1,
        )

    crop = image[cy0:cy1, cx0:cx1]
    return [(rect, occupancy_ratio(crop))]


def build_multi_cell_fallback_regions(
    page: fitz.Page,
    image: np.ndarray,
    width_px: int,
    height_px: int,
) -> list[tuple[RegionRect, float]]:
    for columns, rows in fallback_grids(page):
        if columns != 1 or rows < 4:
            continue

        cell_width = width_px / columns
        cell_height = height_px / rows
        occupied_cells: list[tuple[int, int, int, int, int, int, float]] = []

        for row in range(rows):
            column = 0
            cx0 = round(column * cell_width)
            cy0 = round(row * cell_height)
            cx1 = round((column + 1) * cell_width)
            cy1 = round((row + 1) * cell_height)
            crop = image[cy0:cy1, cx0:cx1]
            ratio = occupancy_ratio(crop)
            if ratio >= 0.02:
                occupied_cells.append((row, column, cx0, cy0, cx1, cy1, ratio))

        occupied_rows = [cell[0] for cell in occupied_cells]
        expected_rows = list(range(len(occupied_rows)))
        if len(occupied_rows) < 3 or occupied_rows != expected_rows or occupied_rows[-1] >= rows - 1:
            continue

        regions: list[tuple[RegionRect, float]] = []
        for row, column, cx0, cy0, cx1, cy1, ratio in occupied_cells:
            rect = RegionRect(
                x0=page.rect.x0 + (column / columns) * page.rect.width,
                y0=page.rect.y0 + (row / rows) * page.rect.height,
                x1=page.rect.x0 + ((column + 1) / columns) * page.rect.width,
                y1=page.rect.y0 + ((row + 1) / rows) * page.rect.height,
            )
            regions.append((rect, ratio))

        if len(regions) > 1:
            return regions

    return []


def trim_custom_region_to_content_bounds(
    page: fitz.Page,
    rect: RegionRect,
    content_x0_px: int,
    content_x1_px: int,
    content_y0_px: int,
    content_y1_px: int,
    image_width_px: int,
    image_height_px: int,
    crop_x0_px: int,
    crop_x1_px: int,
    crop_y0_px: int,
    crop_y1_px: int,
) -> tuple[RegionRect, int, int, int, int]:
    content_x0_pt = page.rect.x0 + (content_x0_px / image_width_px) * page.rect.width
    content_x1_pt = page.rect.x0 + (content_x1_px / image_width_px) * page.rect.width
    content_y0_pt = page.rect.y0 + (content_y0_px / image_height_px) * page.rect.height
    content_y1_pt = page.rect.y0 + (content_y1_px / image_height_px) * page.rect.height
    safety_pt = 0

    trimmed_x0 = max(rect.x0, content_x0_pt - safety_pt)
    trimmed_x1 = min(rect.x1, content_x1_pt + safety_pt)
    trimmed_y0 = max(rect.y0, content_y0_pt - safety_pt)
    trimmed_y1 = min(rect.y1, content_y1_pt + safety_pt)
    if trimmed_x1 <= trimmed_x0 or trimmed_y1 <= trimmed_y0:
        return rect, crop_x0_px, crop_x1_px, crop_y0_px, crop_y1_px

    if (
        abs(trimmed_x0 - rect.x0) < 8
        and abs(rect.x1 - trimmed_x1) < 8
        and abs(trimmed_y0 - rect.y0) < 8
        and abs(rect.y1 - trimmed_y1) < 8
    ):
        return rect, crop_x0_px, crop_x1_px, crop_y0_px, crop_y1_px

    start_x_shift_px = round((trimmed_x0 - rect.x0) / page.rect.width * image_width_px)
    end_x_shift_px = round((rect.x1 - trimmed_x1) / page.rect.width * image_width_px)
    start_shift_px = round((trimmed_y0 - rect.y0) / page.rect.height * image_height_px)
    end_shift_px = round((rect.y1 - trimmed_y1) / page.rect.height * image_height_px)
    return (
        RegionRect(x0=trimmed_x0, y0=trimmed_y0, x1=trimmed_x1, y1=trimmed_y1),
        max(0, crop_x0_px + start_x_shift_px),
        min(image_width_px, crop_x1_px - end_x_shift_px),
        max(0, crop_y0_px + start_shift_px),
        min(image_height_px, crop_y1_px - end_shift_px),
    )


def fallback_grids(page: fitz.Page) -> list[tuple[int, int]]:
    if page.rect.width >= page.rect.height:
        return [
            (1, 4),
            (1, 3),
            (4, 2),
            (3, 4),
            (3, 2),
            (2, 2),
            (2, 1),
            (1, 2),
            (1, 1),
        ]

    return [
        (1, 6),
        (1, 4),
        (1, 3),
        (2, 4),
        (2, 2),
        (1, 2),
        (2, 1),
        (1, 1),
    ]


def content_bounds_px(image: np.ndarray) -> tuple[int, int, int, int] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    mask = gray < 245
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def occupancy_ratio(image: np.ndarray) -> float:
    height, width = image.shape[:2]
    inset_x = max(4, int(width * 0.025))
    inset_y = max(4, int(height * 0.025))
    inner = image[inset_y : height - inset_y, inset_x : width - inset_x]
    if inner.size == 0:
        return 0

    gray = cv2.cvtColor(inner, cv2.COLOR_RGB2GRAY)
    non_white = gray < 245
    return float(np.count_nonzero(non_white) / non_white.size)


def score_confidence(label_type: str, occupancy_ratio: float, lines_found: bool) -> Confidence:
    if occupancy_ratio < 0.0025:
        return Confidence.low
    if label_type != "custom" and lines_found:
        return Confidence.high
    if label_type != "custom":
        return Confidence.medium
    return Confidence.low
