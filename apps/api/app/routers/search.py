from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_ingestion_service, get_repository
from app.models.api import SearchRequest, SearchResponse
from app.models.paper import Paper, jaccard_similarity, tokenize_text
from app.models.report import SearchRun
from app.repositories.sqlite import SQLiteRepository
from app.services.ingestion.service import IngestionService

router = APIRouter(tags=["search"])


@router.get("/search/autocomplete")
async def get_autocomplete(
    q: str = Query(default=""),
    limit: int = Query(default=5, ge=1, le=20),
    repository: SQLiteRepository = Depends(get_repository),
) -> dict:
    queries = repository.get_popular_queries(q, limit)
    return {"popular": queries}


@router.post("/search", response_model=SearchResponse)
async def search_papers(
    request: SearchRequest,
    year_min: int | None = Query(default=None),
    year_max: int | None = Query(default=None),
    min_citations: int = Query(default=0, ge=0),
    sources: str | None = Query(default=None),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    repository: SQLiteRepository = Depends(get_repository),
) -> SearchResponse:
    selected_sources = (
        [source.strip() for source in sources.split(",") if source.strip()]
        if sources
        else request.sources
    )
    result = await ingestion_service.search(
        query=request.query,
        sources=selected_sources,
        max_results=request.max_results,
    )
    filtered_papers, additional_filtered = _apply_search_filters(
        papers=result.papers,
        year_min=year_min,
        year_max=year_max,
        min_citations=min_citations,
    )
    ranked_papers = _rank_papers(request.query, filtered_papers)
    total_filter_removed = result.filter_removed + additional_filtered
    search_run = SearchRun(
        query=request.query,
        sources=selected_sources,
        max_results=request.max_results,
        total_papers=len(ranked_papers),
        dedup_removed=result.dedup_removed,
        filter_removed=total_filter_removed,
        warnings=result.warnings,
    )
    repository.save_search_run(search_run, ranked_papers)
    return SearchResponse(
        search_run_id=search_run.id,
        query=request.query,
        total=len(ranked_papers),
        sources_searched=result.sources_searched,
        papers=ranked_papers,
        dedup_removed=result.dedup_removed,
        filter_removed=total_filter_removed,
        warnings=result.warnings,
    )


def _apply_search_filters(
    papers: list[Paper],
    year_min: int | None,
    year_max: int | None,
    min_citations: int,
) -> tuple[list[Paper], int]:
    filtered: list[Paper] = []
    removed = 0
    for paper in papers:
        if year_min is not None and (paper.year is None or paper.year < year_min):
            removed += 1
            continue
        if year_max is not None and (paper.year is None or paper.year > year_max):
            removed += 1
            continue
        if (paper.citation_count or 0) < min_citations:
            removed += 1
            continue
        filtered.append(paper)
    return filtered, removed


def _rank_papers(query: str, papers: list[Paper]) -> list[Paper]:
    max_citations = (
        max((paper.citation_count or 0) for paper in papers) if papers else 0
    )
    current_year = datetime.now().year
    for paper in papers:
        normalized_citation_count = (
            (paper.citation_count or 0) / max_citations if max_citations else 0.0
        )
        query_overlap = jaccard_similarity(
            query,
            f"{paper.title} {paper.abstract or ''}",
            drop_stop_words=True,
        )
        recency_score = 0.0
        if paper.year is not None and current_year > 1990:
            recency_score = max(
                0.0, min(1.0, (paper.year - 1990) / (current_year - 1990))
            )
        paper.relevance_score = round(
            (0.4 * normalized_citation_count)
            + (0.3 * query_overlap)
            + (0.3 * recency_score),
            4,
        )
    return sorted(
        papers,
        key=lambda paper: (
            paper.relevance_score or 0.0,
            paper.citation_count or 0,
            len(tokenize_text(paper.abstract or "", drop_stop_words=True)),
        ),
        reverse=True,
    )
