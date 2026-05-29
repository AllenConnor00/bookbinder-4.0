from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import CalibrationRequest, ContactSheetRequest, ExportResult, ImpositionPlan, ImpositionSettings, PdfInspectResult, PreviewRequest
from .pdf_engine import create_calibration_page, create_contact_sheet, export_job, inspect_pdf, plan_for_job, render_preview, save_upload


app = FastAPI(title="Bookbinder 4", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/pdf/inspect", response_model=PdfInspectResult)
async def inspect_upload(file: UploadFile = File(...)) -> PdfInspectResult:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please choose a PDF file.")
    data = await file.read()
    job_id, path = save_upload(file.filename, data)
    return inspect_pdf(path, job_id)


@app.post("/api/imposition/plan", response_model=ImpositionPlan)
def create_plan(settings: ImpositionSettings) -> ImpositionPlan:
    try:
        return plan_for_job(settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/imposition/export", response_model=ExportResult)
def export(settings: ImpositionSettings) -> ExportResult:
    try:
        return export_job(settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/preview/{job_id}/{sheet_index}")
def preview(job_id: str, sheet_index: int) -> FileResponse:
    try:
        return FileResponse(render_preview(ImpositionSettings(job_id=job_id), sheet_index), media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/preview/render")
def preview_render(request: PreviewRequest) -> FileResponse:
    try:
        return FileResponse(render_preview(request.settings, request.sheet_index, request.side), media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/preview/contact-sheet")
def contact_sheet(request: ContactSheetRequest) -> FileResponse:
    try:
        return FileResponse(create_contact_sheet(request.settings), media_type="application/pdf", filename="bookbinder4-preview-contact-sheet.pdf")
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tools/calibration")
def calibration(request: CalibrationRequest) -> FileResponse:
    try:
        return FileResponse(create_calibration_page(request.paper, request.print_safe_margin), media_type="application/pdf", filename="bookbinder4-printer-calibration.pdf")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
