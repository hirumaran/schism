from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .claim import PaperClaim
from .contradiction import ContradictionMode, ContradictionPair
from .paper import Paper, normalize_query


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    ingesting = "ingesting"
    embedding = "embedding"
    analyzing = "analyzing"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class SearchRun(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"search_{uuid4().hex[:12]}")
    query: str
    sources: list[str]
    max_results: int
    total_papers: int = 0
    dedup_removed: int = 0
    filter_removed: int = 0
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClaimCluster(BaseModel):
    id: str
    paper_ids: list[str]
    claim_texts: list[str]
    average_similarity: float | None = None
    paper_count: int = 0
    avg_year: float | None = None
    year_range: list[int] = Field(default_factory=list)
    top_terms: list[str] = Field(default_factory=list)
    trimmed_count: int = 0
    fallback_used: bool = False


class InputPaperMetadata(BaseModel):
    title: str | None = None
    filename: str | None = None
    claims_extracted: int = 0
    search_queries_used: list[str] = Field(default_factory=list)


class AnalysisJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:12]}")
    query: str
    normalized_query: str = ""
    mode: ContradictionMode = ContradictionMode.corpus_vs_corpus
    provider: str = "mock"
    model: str | None = None
    status: JobStatus = JobStatus.pending
    progress: int = 0
    paper_count: int = 0
    extracted_claim_count: int = 0
    skipped_claim_count: int = 0
    cluster_count: int = 0
    filtered_pair_count: int = 0
    scored_pair_count: int = 0
    contradiction_count: int = 0
    cached_pair_count: int = 0
    has_contradictions: bool = False
    error: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def model_post_init(self, __context: object) -> None:
        if not self.normalized_query:
            self.normalized_query = normalize_query(self.query)

    @property
    def duration_ms(self) -> int | None:
        if self.completed_at is None:
            return None
        return int((self.completed_at - self.created_at).total_seconds() * 1000)


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    job_id: str | None = None
    search_run_id: str | None = None
    query: str | None = None
    mode: ContradictionMode = ContradictionMode.corpus_vs_corpus
    provider: str = "mock"
    model: str | None = None
    status: JobStatus = JobStatus.done
    contradiction_threshold: float
    has_contradictions: bool = False
    papers: list[Paper] = Field(default_factory=list)
    claims: list[PaperClaim] = Field(default_factory=list)
    clusters: list[ClaimCluster] = Field(default_factory=list)
    contradictions: list[ContradictionPair] = Field(default_factory=list)
    methodological_differences: list[ContradictionPair] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    input_paper: InputPaperMetadata | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
