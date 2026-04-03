from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .claim import PaperClaim
from .contradiction import ContradictionPair
from .paper import Paper


class SearchRun(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"search_{uuid4().hex[:12]}")
    query: str
    sources: list[str]
    max_results: int
    total_papers: int = 0
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClaimCluster(BaseModel):
    id: str
    paper_ids: list[str]
    claim_texts: list[str]
    average_similarity: float | None = None


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"report_{uuid4().hex[:12]}")
    search_run_id: str | None = None
    query: str | None = None
    provider: str = "mock"
    model: str | None = None
    contradiction_threshold: float
    papers: list[Paper] = Field(default_factory=list)
    claims: list[PaperClaim] = Field(default_factory=list)
    clusters: list[ClaimCluster] = Field(default_factory=list)
    contradictions: list[ContradictionPair] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

