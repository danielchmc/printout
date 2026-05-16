from __future__ import annotations

from pathlib import Path
import sys

import cv2
import fitz
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pdf.render import render_page_to_rgb


def main() -> None:
    for path in sorted((ROOT / "testobjects").glob("*.pdf")):
        with fitz.open(path) as document:
            page = document[0]
            image = render_page_to_rgb(page, dpi=120)
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            mask = gray < 245
            ys, xs = np.where(mask)
            print(f"\n{path.name} page={page.rect}")
            if len(xs) == 0:
                print("  no non-white content")
                continue
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            print(f"  px bbox=({x0},{y0},{x1},{y1}) image={image.shape[1]}x{image.shape[0]}")
            print(
                "  pt bbox="
                f"({x0 / image.shape[1] * page.rect.width:.1f},"
                f"{y0 / image.shape[0] * page.rect.height:.1f},"
                f"{x1 / image.shape[1] * page.rect.width:.1f},"
                f"{y1 / image.shape[0] * page.rect.height:.1f})"
            )


if __name__ == "__main__":
    main()
