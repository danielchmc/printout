from __future__ import annotations

from pathlib import Path
import sys

import fitz


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pdf.analyze import analyze_uploads
from app.pdf.compose import compose_output_pdf
from app.pdf.constants import A4_HEIGHT_PT, A4_WIDTH_PT

SMOKE_ROOT = ROOT / "var" / "smoke"


def main() -> None:
    SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    source_pdf = SMOKE_ROOT / "sample-a6-grid.pdf"
    output_pdf = SMOKE_ROOT / "mixed-output.pdf"

    create_sample_pdf(source_pdf)
    reports = analyze_uploads([source_pdf])
    regions = [region for report in reports for region in report.regions if region.occupied]

    print(f"pages={reports[0].page_count}")
    print(f"detected_regions={len(reports[0].regions)}")
    print(f"occupied_regions={len(regions)}")
    print("labels=" + ",".join(region.label_type for region in regions))

    if len(regions) < 2:
        raise SystemExit("Expected at least two occupied regions in smoke test.")

    compose_output_pdf(regions, output_pdf)
    if not output_pdf.exists():
        raise SystemExit("Expected output PDF to be created.")

    print(f"output={output_pdf}")


def create_sample_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=A4_WIDTH_PT, height=A4_HEIGHT_PT)

    half_w = A4_WIDTH_PT / 2
    half_h = A4_HEIGHT_PT / 2
    page.draw_line((half_w, 0), (half_w, A4_HEIGHT_PT), color=(0, 0, 0), width=1)
    page.draw_line((0, half_h), (A4_WIDTH_PT, half_h), color=(0, 0, 0), width=1)

    page.insert_text((48, 88), "A6 price sign", fontsize=28, color=(0, 0, 0))
    page.insert_text((half_w + 48, half_h + 88), "Another sign", fontsize=28, color=(0, 0, 0))
    page.draw_rect((48, 120, 220, 200), color=(0, 0, 0), width=1)
    page.draw_rect((half_w + 48, half_h + 120, half_w + 220, half_h + 200), color=(0, 0, 0), width=1)

    document.save(path)
    document.close()


if __name__ == "__main__":
    main()
