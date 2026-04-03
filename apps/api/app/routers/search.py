from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_ingestion_service, get_repository
from app.models.api import SearchRequest, SearchResponse
from app.models.report import SearchRun
from app.repositories.sqlite import SQLiteRepository
from app.services.ingestion.service import IngestionService

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_papers(
    request: SearchRequest,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    repository: SQLiteRepository = Depends(get_repository),
) -> SearchResponse:
    result = await ingestion_service.search(
        query=request.query,
        sources=request.sources,
        max_results=request.max_results,
    )
    search_run = SearchRun(
        query=request.query,
        sources=request.sources,
        max_results=request.max_results,
        total_papers=len(result.papers),
        warnings=result.warnings,
    )
    repository.save_search_run(search_run, result.papers)
    return SearchResponse(
        search_run_id=search_run.id,
        query=request.query,
        papers=result.papers,
        warnings=result.warnings,
    )

