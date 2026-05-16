from __future__ import annotations

from pathlib import Path

import fitz
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models import DetectedRegion, GenerateSettings, JobStatus, StoredJob
from app.pdf.analyze import analyze_uploads
from app.pdf.compose import compose_output_pdf
from app.pdf.pack import pack_regions
from app.storage import create_job_dir, save_uploads


app = FastAPI(title="Mixed-Format Printout PDF Tool")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_ROOT = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

JOBS: dict[str, StoredJob] = {}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/jobs")
async def create_job(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one PDF.")

    for upload in files:
        if upload.content_type not in {"application/pdf", "application/x-pdf"} and not (upload.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{upload.filename} does not look like a PDF.")

    job_id, job_root = create_job_dir()
    try:
        saved_paths = await save_uploads(job_root, files)
        reports = analyze_uploads(saved_paths)
        job = StoredJob(id=job_id, status=JobStatus.analyzed, root=job_root, files=reports)
        JOBS[job_id] = job
        return job.to_report()
    except Exception as exc:
        job = StoredJob(id=job_id, status=JobStatus.failed, root=job_root, files=[], error=str(exc))
        JOBS[job_id] = job
        raise HTTPException(status_code=500, detail=f"Could not analyze upload: {exc}") from exc


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _get_job(job_id).to_report()


@app.post("/api/jobs/{job_id}/layout")
def preview_layout(job_id: str, settings: GenerateSettings):
    job = _get_job(job_id)
    selected_regions = _selected_regions(job, settings)
    if not selected_regions:
        raise HTTPException(status_code=400, detail="No occupied regions selected.")

    placements = pack_regions(selected_regions, allow_rotation=settings.allow_rotation)
    pages = [
        {"index": index, "width_pt": placement.page_width_pt, "height_pt": placement.page_height_pt}
        for index, placement in enumerate(_first_placement_per_page(placements))
    ]
    return {"pages": pages, "placements": placements}


@app.get("/api/jobs/{job_id}/regions/{region_id}/preview.png")
def region_preview(job_id: str, region_id: str):
    job = _get_job(job_id)
    region = _find_region(job, region_id)
    preview_path = job.root / "previews" / f"{region_id}.png"
    if not preview_path.exists():
        render_region_preview(region, preview_path)
    return FileResponse(preview_path, media_type="image/png")


@app.post("/api/jobs/{job_id}/generate")
def generate_pdf(job_id: str, settings: GenerateSettings):
    job = _get_job(job_id)
    selected_regions = _selected_regions(job, settings)

    if not selected_regions:
        raise HTTPException(status_code=400, detail="No occupied regions selected.")

    output_path = job.root / "outputs" / settings.output_filename
    compose_output_pdf(
        selected_regions,
        output_path=output_path,
        add_cut_lines=settings.add_cut_lines,
        allow_rotation=settings.allow_rotation,
    )
    job.output_pdf = output_path
    job.status = JobStatus.generated
    return job.to_report()


@app.get("/api/jobs/{job_id}/download")
def download_pdf(job_id: str):
    job = _get_job(job_id)
    if not job.output_pdf or not job.output_pdf.exists():
        raise HTTPException(status_code=404, detail="This job has no generated PDF yet.")

    return FileResponse(
        job.output_pdf,
        media_type="application/pdf",
        filename=job.output_pdf.name,
    )


def _get_job(job_id: str) -> StoredJob:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _all_regions(job: StoredJob) -> list[DetectedRegion]:
    return [region for source in job.files for region in source.regions]


def _selected_regions(job: StoredJob, settings: GenerateSettings) -> list[DetectedRegion]:
    all_regions = _all_regions(job)
    selected_ids = set(settings.include_region_ids or [])
    if selected_ids:
        return [region for region in all_regions if region.id in selected_ids]
    return [region for region in all_regions if region.occupied]


def _find_region(job: StoredJob, region_id: str) -> DetectedRegion:
    for region in _all_regions(job):
        if region.id == region_id:
            return region
    raise HTTPException(status_code=404, detail="Region not found.")


def _first_placement_per_page(placements):
    seen: set[int] = set()
    first = []
    for placement in placements:
        if placement.page_index not in seen:
            seen.add(placement.page_index)
            first.append(placement)
    return first


def render_region_preview(region: DetectedRegion, preview_path: Path) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(region.source_path) as document:
        page = document[region.page_index]
        clip = fitz.Rect(region.rect.x0, region.rect.y0, region.rect.x1, region.rect.y1)
        zoom = min(2.0, 360 / max(clip.width, clip.height))
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        pixmap.save(preview_path)
