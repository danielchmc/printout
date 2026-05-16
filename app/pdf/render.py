from __future__ import annotations

import fitz
import numpy as np

from app.pdf.constants import POINTS_PER_INCH


def render_page_to_rgb(page: fitz.Page, dpi: int = 200) -> np.ndarray:
    zoom = dpi / POINTS_PER_INCH
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8)
    return image.reshape(pixmap.height, pixmap.width, pixmap.n)
