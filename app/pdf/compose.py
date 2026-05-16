from __future__ import annotations

from pathlib import Path

import fitz

from app.models import DetectedRegion, Placement
from app.pdf.pack import pack_regions


def compose_output_pdf(
    regions: list[DetectedRegion],
    output_path: Path,
    add_cut_lines: bool = True,
    allow_rotation: bool = False,
) -> Path:
    placements = pack_regions(regions, allow_rotation=allow_rotation)
    output = fitz.open()

    page_sizes: list[tuple[float, float]] = []
    page_count = max((placement.page_index for placement in placements), default=-1) + 1
    for page_index in range(page_count):
        placement = next(item for item in placements if item.page_index == page_index)
        page_sizes.append((placement.page_width_pt, placement.page_height_pt))
        output.new_page(width=placement.page_width_pt, height=placement.page_height_pt)

    source_documents: dict[str, fitz.Document] = {}
    try:
        for placement in placements:
            source_path = placement.region.source_path
            source = source_documents.get(source_path)
            if source is None:
                source = fitz.open(source_path)
                source_documents[source_path] = source

            page = output[placement.page_index]
            source_rect = fitz.Rect(
                placement.region.rect.x0,
                placement.region.rect.y0,
                placement.region.rect.x1,
                placement.region.rect.y1,
            )
            target_rect = fitz.Rect(
                placement.rect.x0,
                placement.rect.y0,
                placement.rect.x1,
                placement.rect.y1,
            )
            rotate = 90 if placement.rotated else 0
            page.show_pdf_page(target_rect, source, placement.region.page_index, clip=source_rect, rotate=rotate)

        if add_cut_lines:
            draw_merged_cut_lines(output, placements)

        output.save(output_path)
        return output_path
    finally:
        output.close()
        for document in source_documents.values():
            document.close()


def draw_merged_cut_lines(document: fitz.Document, placements: list[Placement]) -> None:
    by_page: dict[int, list[Placement]] = {}
    for placement in placements:
        by_page.setdefault(placement.page_index, []).append(placement)

    for page_index, page_placements in by_page.items():
        horizontal: dict[int, list[tuple[int, int]]] = {}
        vertical: dict[int, list[tuple[int, int]]] = {}

        for placement in page_placements:
            rect = placement.rect
            x0 = _line_coord(rect.x0)
            y0 = _line_coord(rect.y0)
            x1 = _line_coord(rect.x1)
            y1 = _line_coord(rect.y1)

            horizontal.setdefault(y0, []).append((x0, x1))
            horizontal.setdefault(y1, []).append((x0, x1))
            vertical.setdefault(x0, []).append((y0, y1))
            vertical.setdefault(x1, []).append((y0, y1))

        page = document[page_index]
        for y, intervals in horizontal.items():
            for x0, x1 in _merge_intervals(intervals):
                page.draw_line((_pt(x0), _pt(y)), (_pt(x1), _pt(y)), color=(0, 0, 0), width=0.5)

        for x, intervals in vertical.items():
            for y0, y1 in _merge_intervals(intervals):
                page.draw_line((_pt(x), _pt(y0)), (_pt(x), _pt(y1)), color=(0, 0, 0), width=0.5)


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []

    ordered = sorted((min(start, end), max(start, end)) for start, end in intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _line_coord(value: float) -> int:
    return round(value * 10)


def _pt(value: int) -> float:
    return value / 10
