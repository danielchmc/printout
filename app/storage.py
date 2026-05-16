from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.models import StoredJob


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "var" / "jobs"


def create_job_dir() -> tuple[str, Path]:
    job_id = uuid.uuid4().hex
    job_root = DATA_ROOT / job_id
    (job_root / "uploads").mkdir(parents=True, exist_ok=False)
    (job_root / "previews").mkdir(parents=True, exist_ok=True)
    (job_root / "outputs").mkdir(parents=True, exist_ok=True)
    return job_id, job_root


def safe_pdf_name(filename: str) -> str:
    name = Path(filename).name
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return "".join(char for char in name if char.isalnum() or char in "._- ").strip()


async def save_uploads(job_root: Path, files: list[UploadFile]) -> list[Path]:
    saved: list[Path] = []
    upload_root = job_root / "uploads"
    for index, upload in enumerate(files, start=1):
        filename = safe_pdf_name(upload.filename or f"upload-{index}.pdf")
        target = upload_root / f"{index:02d}-{filename}"
        with target.open("wb") as destination:
            while chunk := await upload.read(1024 * 1024):
                destination.write(chunk)
        saved.append(target)
    return saved


def clear_all_jobs() -> None:
    if DATA_ROOT.exists():
        shutil.rmtree(DATA_ROOT)
