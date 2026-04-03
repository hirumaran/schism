from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .contradiction import ContradictionMode, ContradictionPair, ContradictionType
from .paper import Paper
from .report import AnalysisJob, AnalysisReport, JobStatus


def default_sources() -> list[str]:
    return ["arxiv", "semantic_scholar", "openalex", "pubmed"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=2)
    max_results: int = Field(default=25, ge=1, le=200)
    sources: list[str] = Field(default_factory=default_sources)


class SearchResponse(BaseModel):
    search_run_id: str
    query: str
    total: int
    sources_searched: list[str]
    papers: list[Paper]
    dedup_removed: int = 0
    filter_removed: int = 0
    warnings: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    query: str | None = None
    paper_ids: list[str] = Field(default_factory=list)
    max_results: int = Field(default=25, ge=1, le=200)
    sources: list[str] = Field(default_factory=default_sources)
    contradiction_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    cluster_similarity_threshold: float = Field(default=0.78, ge=0.0, le=1.0)
    min_keyword_overlap: int = Field(default=1, ge=0, le=20)
    min_claim_quality: float = Field(default=0.3, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_inputs(self) -> "AnalyzeRequest":
        if not self.query and not self.paper_ids:
            raise ValueError("Provide either a query or explicit paper_ids.")
        return self


class AnalyzePaperTextRequest(BaseModel):
    text: str = Field(min_length=100)
    title: str | None = None
    max_results: int = Field(default=50, ge=1, le=200)
    sources: list[str] = Field(default_factory=lambda: ["arxiv", "semantic_scholar"])


class ExportFormat(str, Enum):
    json = "json"
    csv = "csv"


class JobStatsResponse(BaseModel):
    job_id: str
    query: str
    status: str
    paper_count: int
    extracted_claim_count: int
    skipped_claim_count: int
    cluster_count: int
    filtered_pair_count: int
    scored_pair_count: int
    contradiction_count: int
    cache_hit_rate: float
    duration_ms: int | None
    cost_estimate: dict[str, int]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyzeResponse(AnalysisReport):
    pass


class AnalyzeAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobResultsResponse(BaseModel):
    job_id: str
    query: str
    total: int
    results: list[ContradictionPair]


class JobResultsFilter(BaseModel):
    type: ContradictionType | None = None
    mode: ContradictionMode | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class JobLookupResponse(AnalysisJob):
    pass
