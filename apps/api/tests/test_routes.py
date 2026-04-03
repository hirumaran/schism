from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_analysis_service, get_paper_input_parser, get_repository
from app.main import app
from app.models.contradiction import ContradictionMode, ContradictionPair, ContradictionType
from app.models.paper import Paper
from app.models.report import AnalysisJob, AnalysisReport, JobStatus
from app.repositories.sqlite import SQLiteRepository
from app.services.paper_input import ExtractedSections, PaperInputParser, ParsedInput


class StubAnalysisService:
    def __init__(self, job: AnalysisJob, stats: dict[str, object]) -> None:
        self.job = job
        self.stats = stats

    async def run_analysis(self, request, context):
        return self.job, None, 202

    async def run_paper_analysis(self, *, parsed_input, sections, max_results, sources, context):
        return self.job, None, 202

    def get_job(self, job_id: str):
        return self.job if job_id == self.job.id else None

    def get_job_results(self, job_id: str, *, contradiction_type, mode, limit, offset):
        if job_id != self.job.id:
            return None
        input_paper = Paper(
            id=f"input_{job_id}",
            source="user_input",
            external_id=job_id,
            title="User-provided paper",
            abstract=" ".join(["word"] * 100),
        )
        found_paper = Paper(
            source="stub",
            external_id="paper_b",
            title="Found paper",
            abstract=" ".join(["word"] * 100),
            year=2023,
        )
        pair = ContradictionPair(
            paper_a_id=input_paper.id,
            paper_b_id=found_paper.id,
            mode=ContradictionMode.paper_vs_corpus,
            raw_score=0.8,
            score=0.8,
            type=ContradictionType.direct,
            explanation="Conflicting findings.",
            is_contradiction=True,
            paper_a=input_paper,
            paper_b=found_paper,
            paper_a_claim="Omega 3 reduces cardiovascular risk in adults over time",
            paper_b_claim="Omega 3 has no cardiovascular benefit in adults over time",
        )
        return {
            "job_id": job_id,
            "query": self.job.query,
            "total": 1,
            "results": [pair.model_dump(mode="json")],
        }

    def get_job_stats(self, job_id: str):
        return self.stats if job_id == self.job.id else None

    async def cancel_or_delete_job(self, job_id: str) -> bool:
        return job_id == self.job.id

    async def start_watchdog(self) -> None:
        return None

    async def stop_watchdog(self) -> None:
        return None


class StubPaperInputParser(PaperInputParser):
    async def parse_text(self, text: str, title: str | None) -> ParsedInput:
        return ParsedInput(text=text, title=title)

    async def parse_upload(self, file):
        return ParsedInput(text=" ".join(["paper"] * 100), filename=file.filename)

    def extract_sections(self, text: str) -> ExtractedSections:
        return ExtractedSections(abstract=text[:200], conclusion=None, full_text=text, best_section=text[:200])


def build_job() -> AnalysisJob:
    return AnalysisJob(
        id="job_test123",
        query="omega-3 cardiovascular",
        mode=ContradictionMode.paper_vs_corpus,
        provider="mock",
        status=JobStatus.pending,
        progress=0,
    )


def test_job_stats_endpoint_returns_cost_estimate() -> None:
    job = build_job()
    stats = {
        "job_id": job.id,
        "query": job.query,
        "status": "done",
        "paper_count": 2,
        "extracted_claim_count": 2,
        "skipped_claim_count": 0,
        "cluster_count": 1,
        "filtered_pair_count": 0,
        "scored_pair_count": 1,
        "contradiction_count": 1,
        "cache_hit_rate": 0.0,
        "duration_ms": 100,
        "cost_estimate": {
            "claim_extraction_tokens": 600,
            "contradiction_scoring_tokens": 400,
            "total_tokens": 1000,
        },
        "metadata": {},
    }
    app.dependency_overrides[get_analysis_service] = lambda: StubAnalysisService(job, stats)
    client = TestClient(app)
    response = client.get(f"/api/jobs/{job.id}/stats")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["cost_estimate"]["total_tokens"] == 1000


def test_analyze_route_sets_x_cache_header_on_cached_result() -> None:
    job = build_job()

    class CachedAnalysisService(StubAnalysisService):
        async def run_analysis(self, request, context):
            cached = self.job.model_copy(update={"status": JobStatus.done, "progress": 100})
            return cached, "HIT", 200

    app.dependency_overrides[get_analysis_service] = lambda: CachedAnalysisService(job, {"job_id": job.id, "query": job.query, "status": "done", "paper_count": 0, "extracted_claim_count": 0, "skipped_claim_count": 0, "cluster_count": 0, "filtered_pair_count": 0, "scored_pair_count": 0, "contradiction_count": 0, "cache_hit_rate": 1.0, "duration_ms": 0, "cost_estimate": {"claim_extraction_tokens": 0, "contradiction_scoring_tokens": 0, "total_tokens": 0}, "metadata": {}})
    client = TestClient(app)
    response = client.post("/api/analyze", json={"query": "omega-3 cardiovascular"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.headers["x-cache"] == "HIT"
    assert response.json()["job_id"] == job.id


def test_analyze_paper_text_endpoint() -> None:
    job = build_job()
    stats = {"job_id": job.id, "query": job.query, "status": "pending", "paper_count": 0, "extracted_claim_count": 0, "skipped_claim_count": 0, "cluster_count": 0, "filtered_pair_count": 0, "scored_pair_count": 0, "contradiction_count": 0, "cache_hit_rate": 0.0, "duration_ms": None, "cost_estimate": {"claim_extraction_tokens": 0, "contradiction_scoring_tokens": 0, "total_tokens": 0}, "metadata": {}}
    app.dependency_overrides[get_analysis_service] = lambda: StubAnalysisService(job, stats)
    app.dependency_overrides[get_paper_input_parser] = lambda: StubPaperInputParser()
    client = TestClient(app)
    response = client.post(
        "/api/analyze/paper",
        json={"text": " ".join(["evidence"] * 120), "title": "My Paper"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 202
    assert "job_id" in response.json()


def test_analyze_paper_returns_immediately() -> None:
    job = build_job()
    stats = {"job_id": job.id, "query": job.query, "status": "pending", "paper_count": 0, "extracted_claim_count": 0, "skipped_claim_count": 0, "cluster_count": 0, "filtered_pair_count": 0, "scored_pair_count": 0, "contradiction_count": 0, "cache_hit_rate": 0.0, "duration_ms": None, "cost_estimate": {"claim_extraction_tokens": 0, "contradiction_scoring_tokens": 0, "total_tokens": 0}, "metadata": {}}
    app.dependency_overrides[get_analysis_service] = lambda: StubAnalysisService(job, stats)
    app.dependency_overrides[get_paper_input_parser] = lambda: StubPaperInputParser()
    client = TestClient(app)
    started = time.perf_counter()
    response = client.post(
        "/api/analyze/paper",
        json={"text": " ".join(["evidence"] * 120), "title": "My Paper"},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    app.dependency_overrides.clear()
    assert response.status_code == 202
    assert elapsed_ms < 500


def test_jobs_route_exists() -> None:
    job = build_job()
    stats = {"job_id": job.id, "query": job.query, "status": "pending", "paper_count": 0, "extracted_claim_count": 0, "skipped_claim_count": 0, "cluster_count": 0, "filtered_pair_count": 0, "scored_pair_count": 0, "contradiction_count": 0, "cache_hit_rate": 0.0, "duration_ms": None, "cost_estimate": {"claim_extraction_tokens": 0, "contradiction_scoring_tokens": 0, "total_tokens": 0}, "metadata": {}}
    app.dependency_overrides[get_analysis_service] = lambda: StubAnalysisService(job, stats)
    client = TestClient(app)
    response = client.get(f"/api/jobs/{job.id}")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["id"] == job.id


def test_jobs_results_route_exists() -> None:
    job = build_job()
    stats = {"job_id": job.id, "query": job.query, "status": "pending", "paper_count": 0, "extracted_claim_count": 0, "skipped_claim_count": 0, "cluster_count": 0, "filtered_pair_count": 0, "scored_pair_count": 0, "contradiction_count": 0, "cache_hit_rate": 0.0, "duration_ms": None, "cost_estimate": {"claim_extraction_tokens": 0, "contradiction_scoring_tokens": 0, "total_tokens": 0}, "metadata": {}}
    app.dependency_overrides[get_analysis_service] = lambda: StubAnalysisService(job, stats)
    client = TestClient(app)
    response = client.get(f"/api/jobs/{job.id}/results")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["job_id"] == job.id


def test_export_route_supports_json_and_csv(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'routes.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    report = AnalysisReport(
        id="job_export123",
        job_id="job_export123",
        query="omega-3 cardiovascular",
        mode=ContradictionMode.corpus_vs_corpus,
        provider="mock",
        contradiction_threshold=0.6,
        status=JobStatus.done,
    )
    repository.save_report(report)
    app.dependency_overrides[get_repository] = lambda: repository
    client = TestClient(app)
    json_response = client.get(f"/api/reports/{report.id}/export?format=json")
    csv_response = client.get(f"/api/reports/{report.id}/export?format=csv")
    app.dependency_overrides.clear()
    assert json_response.status_code == 200
    assert "attachment;" in json_response.headers["content-disposition"]
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
