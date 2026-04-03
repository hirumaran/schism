from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from .paper import Paper
from .report import AnalysisReport


def default_sources() -> list[str]:
    return ["arxiv", "semantic_scholar", "openalex", "pubmed"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=2)
    max_results: int = Field(default=25, ge=1, le=200)
    sources: list[str] = Field(default_factory=default_sources)


class SearchResponse(BaseModel):
    search_run_id: str
    query: str
    papers: list[Paper]
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


class ExportFormat(str, Enum):
    json = "json"
    csv = "csv"


class AnalyzeResponse(AnalysisReport):
    pass
