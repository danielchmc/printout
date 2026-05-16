# Mixed-Format Printout PDF Tool

Local web application for combining shop-admin PDF printouts into optimized mixed A4 sheets.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

## GitHub Pages

This project includes a GitHub Actions workflow at `.github/workflows/pages.yml`
that publishes the static UI in `app/static` to GitHub Pages.

GitHub Pages cannot run the FastAPI/Python backend. To use the Pages site, run or
deploy the backend separately, then open the Pages URL with the backend endpoint:

```text
https://YOUR-GITHUB-USER.github.io/YOUR-REPO/?api=https://YOUR-BACKEND.example.com
```

The page saves that endpoint in the browser. When you run the app locally through
Uvicorn, no endpoint is needed because the UI and API share `127.0.0.1:8000`.

To publish:

1. Push this folder to a GitHub repository.
2. In GitHub, open `Settings > Pages`.
3. Set `Build and deployment` to `GitHub Actions`.
4. Push to the `main` branch or run the `Deploy static site to GitHub Pages`
   workflow manually.

## Current MVP

- Upload one or more PDF files.
- Analyze pages for cut-lines and occupied print regions.
- Preview detected regions and confidence.
- Generate a mixed A4 output PDF.
- Download the result.

The PDF analysis engine is intentionally modular so detection, classification, packing, and composition can be improved independently as real shop-admin PDF samples are collected.
