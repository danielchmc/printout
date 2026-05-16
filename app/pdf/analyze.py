from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models import SourceFileReport
from app.pdf.regions import analyze_pdf


def analyze_uploads(paths: list[Path]) -> list[SourceFileReport]:
    reports: list[SourceFileReport] = []
    for path in paths:
        file_id = uuid4().hex
        page_count, regions = analyze_pdf(path, file_id=file_id)
        reports.append(
            SourceFileReport(
                id=file_id,
                filename=path.name,
                page_count=page_count,
                regions=regions,
            )
        )
    return reports
