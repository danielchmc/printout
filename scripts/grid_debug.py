from __future__ import annotations

from pathlib import Path
import sys

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pdf.regions import fallback_grids, occupancy_ratio
from app.pdf.render import render_page_to_rgb


def main() -> None:
    path = ROOT / "testobjects" / "printout-optimizer-a4.pdf"
    with fitz.open(path) as document:
        page = document[0]
        image = render_page_to_rgb(page, dpi=200)
        height, width = image.shape[:2]
        print(path.name, page.rect, f"{width}x{height}")
        for columns, rows in fallback_grids(page):
            print(f"grid {columns}x{rows}")
            cell_width = width / columns
            cell_height = height / rows
            for row in range(rows):
                values = []
                for column in range(columns):
                    x0 = round(column * cell_width)
                    x1 = round((column + 1) * cell_width)
                    y0 = round(row * cell_height)
                    y1 = round((row + 1) * cell_height)
                    values.append(f"{occupancy_ratio(image[y0:y1, x0:x1]):.4f}")
                print("  " + " ".join(values))


if __name__ == "__main__":
    main()
