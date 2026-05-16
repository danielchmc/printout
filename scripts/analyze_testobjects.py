from __future__ import annotations

from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pdf.analyze import analyze_uploads
from app.pdf.compose import compose_output_pdf


def main() -> None:
    source_root = ROOT / "testobjects"
    output_root = ROOT / "var" / "testobjects"
    output_root.mkdir(parents=True, exist_ok=True)

    paths = sorted(source_root.glob("*.pdf"))
    reports = analyze_uploads(paths)
    occupied = []

    for report in reports:
        report_occupied = [region for region in report.regions if region.occupied]
        occupied.extend(report_occupied)
        print(f"\n{report.filename}")
        print(f"  pages={report.page_count} regions={len(report.regions)} occupied={len(report_occupied)}")
        for region in report.regions:
            marker = "x" if region.occupied else "-"
            print(
                f"  {marker} page={region.page_index + 1} "
                f"type={region.label_type:<6} confidence={region.confidence:<6} "
                f"rect=({region.rect.x0:.1f},{region.rect.y0:.1f},{region.rect.x1:.1f},{region.rect.y1:.1f}) "
                f"size={region.width_pt:.1f}x{region.height_pt:.1f} "
                f"occ={region.occupancy_ratio:.4f}"
            )

    output_pdf = output_root / "official-mixed-output.pdf"
    print(f"\nComposing {len(occupied)} occupied regions...")
    try:
        compose_output_pdf(occupied, output_pdf)
    except Exception:
        traceback.print_exc()
        raise
    print(f"output={output_pdf}")


if __name__ == "__main__":
    main()
