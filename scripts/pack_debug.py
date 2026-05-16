from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pdf.analyze import analyze_uploads
from app.pdf.pack import pack_regions


def main() -> None:
    report = analyze_uploads([ROOT / "testobjects" / "product1_a7.pdf"])[0]
    source_region = next(region for region in report.regions if region.occupied)
    regions = [source_region.model_copy(update={"id": f"a7-{index}"}) for index in range(8)]

    for allow_rotation in (False, True):
        placements = pack_regions(regions, allow_rotation=allow_rotation)
        page_count = max(placement.page_index for placement in placements) + 1
        print(f"\nallow_rotation={allow_rotation} pages={page_count}")
        for placement in placements:
            rect = placement.rect
            print(
                f"  page={placement.page_index + 1} rotated={placement.rotated} "
                f"rect=({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}) "
                f"size={rect.width:.1f}x{rect.height:.1f}"
            )


if __name__ == "__main__":
    main()
