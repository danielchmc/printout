from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RegionRect(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


class DetectedRegion(BaseModel):
    id: str
    source_file: str
    source_path: str
    page_index: int
    rect: RegionRect
    width_pt: float
    height_pt: float
    label_type: str
    occupied: bool
    confidence: Confidence
    occupancy_ratio: float = Field(ge=0)


class SourceFileReport(BaseModel):
    id: str
    filename: str
    page_count: int
    regions: list[DetectedRegion]


class JobStatus(str, Enum):
    analyzed = "analyzed"
    generated = "generated"
    failed = "failed"


class JobReport(BaseModel):
    id: str
    status: JobStatus
    files: list[SourceFileReport]
    output_pdf: str | None = None
    error: str | None = None


class GenerateSettings(BaseModel):
    include_region_ids: list[str] | None = None
    add_cut_lines: bool = True
    allow_rotation: bool = False
    output_filename: str = "mixed-printout.pdf"


class Placement(BaseModel):
    region: DetectedRegion
    page_index: int
    rect: RegionRect
    page_width_pt: float
    page_height_pt: float
    rotated: bool = False


class StoredJob(BaseModel):
    id: str
    status: JobStatus
    root: Path
    files: list[SourceFileReport]
    output_pdf: Path | None = None
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    def to_report(self) -> JobReport:
        return JobReport(
            id=self.id,
            status=self.status,
            files=self.files,
            output_pdf=str(self.output_pdf) if self.output_pdf else None,
            error=self.error,
        )
