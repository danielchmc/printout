from __future__ import annotations

from app.models import DetectedRegion, Placement, RegionRect
from app.pdf.constants import A4_HEIGHT_PT, A4_WIDTH_PT


def pack_regions(regions: list[DetectedRegion], allow_rotation: bool = False) -> list[Placement]:
    ordered = sorted(regions, key=lambda region: region.width_pt * region.height_pt, reverse=True)
    pages: list[_Page] = [_Page.portrait()]
    placements: list[Placement] = []

    for region in ordered:
        placement = _place_region(region, pages, allow_rotation)
        placements.append(placement)

    return placements


def _place_region(region: DetectedRegion, pages: list["_Page"], allow_rotation: bool) -> Placement:
    candidates = [(region.width_pt, region.height_pt, False)]
    if allow_rotation:
        candidates.append((region.height_pt, region.width_pt, True))

    best_fit: _Fit | None = None
    for page_index, page in enumerate(pages):
        for free_rect in list(page.free_rects):
            for width, height, rotated in candidates:
                if width <= free_rect.width + 0.1 and height <= free_rect.height + 0.1:
                    fit = _Fit(page_index, page, free_rect, width, height, rotated)
                    if best_fit is None or fit.score() < best_fit.score():
                        best_fit = fit

    if best_fit is not None:
        return best_fit.apply(region)

    new_page = _best_new_page(candidates)
    if new_page is None:
        raise ValueError(
            f"Region {region.id} ({region.width_pt:.1f} x {region.height_pt:.1f} pt) "
            "does not fit on an A4 page at preserved scale."
        )

    pages.append(new_page)
    return _place_region(region, pages, allow_rotation)


def _best_new_page(candidates: list[tuple[float, float, bool]]) -> "_Page | None":
    for width, height, _rotated in candidates:
        if width <= A4_WIDTH_PT + 0.1 and height <= A4_HEIGHT_PT + 0.1:
            return _Page.portrait()
        if width <= A4_HEIGHT_PT + 0.1 and height <= A4_WIDTH_PT + 0.1:
            return _Page.landscape()
    return None


class _Page:
    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.free_rects = [_FreeRect(0, 0, width, height)]

    @classmethod
    def portrait(cls) -> "_Page":
        return cls(A4_WIDTH_PT, A4_HEIGHT_PT)

    @classmethod
    def landscape(cls) -> "_Page":
        return cls(A4_HEIGHT_PT, A4_WIDTH_PT)


class _Fit:
    def __init__(
        self,
        page_index: int,
        page: _Page,
        free_rect: "_FreeRect",
        width: float,
        height: float,
        rotated: bool,
    ) -> None:
        self.page_index = page_index
        self.page = page
        self.free_rect = free_rect
        self.width = width
        self.height = height
        self.rotated = rotated

    def score(self) -> tuple[float, float, float, int, float]:
        split = self.free_rect.split(self.width, self.height)
        largest_remaining = max((rect.area for rect in split), default=0)
        slivers = sum(1 for rect in split if min(rect.width, rect.height) < 24)
        leftover_area = self.free_rect.area - (self.width * self.height)
        max_axis_leftover = max(self.free_rect.width - self.width, self.free_rect.height - self.height)
        return (
            -largest_remaining,
            slivers,
            leftover_area,
            len(split),
            max_axis_leftover,
        )

    def apply(self, region: DetectedRegion) -> Placement:
        self.page.free_rects.remove(self.free_rect)
        self.page.free_rects.extend(self.free_rect.split(self.width, self.height))
        return Placement(
            region=region,
            page_index=self.page_index,
            rect=RegionRect(
                x0=self.free_rect.x,
                y0=self.free_rect.y,
                x1=self.free_rect.x + self.width,
                y1=self.free_rect.y + self.height,
            ),
            page_width_pt=self.page.width,
            page_height_pt=self.page.height,
            rotated=self.rotated,
        )


class _FreeRect:
    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def split(self, used_width: float, used_height: float) -> list["_FreeRect"]:
        remaining: list[_FreeRect] = []
        right_width = self.width - used_width
        bottom_height = self.height - used_height
        if right_width > 8:
            remaining.append(_FreeRect(self.x + used_width, self.y, right_width, used_height))
        if bottom_height > 8:
            remaining.append(_FreeRect(self.x, self.y + used_height, self.width, bottom_height))
        return remaining

    @property
    def area(self) -> float:
        return self.width * self.height
