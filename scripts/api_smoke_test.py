from __future__ import annotations

from pathlib import Path
import json
import mimetypes
import os
import uuid
from urllib import request


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("PRINTOPT_BASE_URL", "http://127.0.0.1:8000")


def main() -> None:
    paths = [
        ROOT / "testobjects" / "product1_a5.pdf",
        ROOT / "testobjects" / "product1_a6.pdf",
        ROOT / "testobjects" / "product1_a7.pdf",
        ROOT / "testobjects" / "product1_shelf.pdf",
    ]
    job = post_files(f"{BASE_URL}/api/jobs", paths)
    regions = [region for file in job["files"] for region in file["regions"] if region["occupied"]]
    print(f"job={job['id']} occupied={len(regions)} labels={','.join(region['label_type'] for region in regions)}")

    layout = post_json(
        f"{BASE_URL}/api/jobs/{job['id']}/layout",
        {
            "include_region_ids": [region["id"] for region in regions],
            "add_cut_lines": True,
            "allow_rotation": True,
            "output_filename": "api-smoke-output.pdf",
        },
    )
    print(f"layout_pages={len(layout['pages'])} placements={len(layout['placements'])}")

    with request.urlopen(f"{BASE_URL}/api/jobs/{job['id']}/regions/{regions[0]['id']}/preview.png", timeout=30) as response:
        preview = response.read()
    if not preview.startswith(b"\x89PNG"):
        raise SystemExit("Region preview did not return a PNG.")
    print(f"preview_bytes={len(preview)}")

    generated = post_json(
        f"{BASE_URL}/api/jobs/{job['id']}/generate",
        {
            "include_region_ids": [region["id"] for region in regions],
            "add_cut_lines": True,
            "allow_rotation": False,
            "output_filename": "api-smoke-output.pdf",
        },
    )
    print(f"status={generated['status']} output={generated['output_pdf']}")

    with request.urlopen(f"{BASE_URL}/api/jobs/{job['id']}/download", timeout=30) as response:
        payload = response.read()
    if not payload.startswith(b"%PDF"):
        raise SystemExit("Download did not return a PDF.")
    print(f"download_bytes={len(payload)}")


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def post_files(url: str, paths: list[Path]) -> dict:
    boundary = f"----printout-{uuid.uuid4().hex}"
    body = bytearray()

    for path in paths:
        content_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    req = request.Request(
        url,
        data=bytes(body),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
