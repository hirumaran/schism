from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_analysis_service
from app.models.api import JobLookupResponse, JobResultsResponse, JobStatsResponse
from app.models.contradiction import ContradictionMode, ContradictionType
from app.services.analysis_service import AnalysisService

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobLookupResponse)
async def get_job(
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> JobLookupResponse:
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobLookupResponse.model_validate(job.model_dump())


@router.get("/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: str,
    type: ContradictionType | None = Query(default=None),
    mode: ContradictionMode | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AnalysisService = Depends(get_analysis_service),
) -> JobResultsResponse:
    payload = service.get_job_results(
        job_id,
        contradiction_type=type,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobResultsResponse.model_validate(payload)


@router.get("/jobs/{job_id}/stats", response_model=JobStatsResponse)
async def get_job_stats(
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> JobStatsResponse:
    payload = service.get_job_stats(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatsResponse.model_validate(payload)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_or_cancel_job(
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> Response:
    deleted = await service.cancel_or_delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
