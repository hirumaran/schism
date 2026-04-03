from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.dependencies import get_report_exporter, get_repository
from app.models.api import AnalyzeResponse, ExportFormat
from app.repositories.sqlite import SQLiteRepository
from app.services.report_exporter import ReportExporter

router = APIRouter(tags=["reports"])


@router.get("/reports/{report_id}", response_model=AnalyzeResponse)
async def get_report(
    report_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> AnalyzeResponse:
    report = repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return AnalyzeResponse.model_validate(report.model_dump())


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    format: ExportFormat = Query(default=ExportFormat.json),
    repository: SQLiteRepository = Depends(get_repository),
    exporter: ReportExporter = Depends(get_report_exporter),
):
    report = repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    if format == ExportFormat.csv:
        return PlainTextResponse(
            content=exporter.to_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{report_id}.csv"'},
        )

    return JSONResponse(content=exporter.to_json_payload(report))

