from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.models.api import AnalyzeRequest
from app.models.contradiction import ContradictionMode
from app.models.report import AnalysisJob, AnalysisReport, JobStatus
from app.repositories.sqlite import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.llm_client import ProviderContext


class CacheOnlyEngine:
    async def analyze(self, request, context, job):  # pragma: no cover - should not run
        raise AssertionError("analyze should not be called on a cache hit")

    async def analyze_paper(self, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("analyze_paper should not be called in this test")


class WaitingEngine:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.released = asyncio.Event()

    async def analyze(self, request, context, job):
        self.started.set()
        await self.released.wait()
        return AnalysisReport(
            id=job.id,
            job_id=job.id,
            query=job.query,
            mode=ContradictionMode.corpus_vs_corpus,
            provider=context.normalized_provider,
            contradiction_threshold=0.6,
            status=JobStatus.done,
        )


def test_run_analysis_returns_cache_hit_for_recent_completed_query(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'analysis-service.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    service = AnalysisService(settings=settings, repository=repository, engine=CacheOnlyEngine())  # type: ignore[arg-type]

    job = AnalysisJob(
        query="omega-3 cardiovascular",
        mode=ContradictionMode.corpus_vs_corpus,
        status=JobStatus.done,
        progress=100,
        completed_at=datetime.now(timezone.utc),
    )
    report = AnalysisReport(
        id=job.id,
        job_id=job.id,
        query=job.query,
        mode=ContradictionMode.corpus_vs_corpus,
        provider="mock",
        contradiction_threshold=0.6,
        status=JobStatus.done,
    )
    repository.create_job(job)
    repository.save_report(report)

    resolved_job, cache_state, status_code = asyncio.run(
        service.run_analysis(
            AnalyzeRequest(query="  OMEGA-3 CARDIOVASCULAR  "),
            ProviderContext(provider="mock"),
        )
    )
    assert cache_state == "HIT"
    assert status_code == 200
    assert resolved_job.id == job.id


def test_run_analysis_returns_immediately_and_starts_background_task(tmp_path: Path) -> None:
    async def exercise() -> None:
        settings = Settings(database_url=f"sqlite:///{tmp_path / 'analysis-service-bg.db'}")
        repository = SQLiteRepository(settings.sqlite_path)
        engine = WaitingEngine()
        service = AnalysisService(settings=settings, repository=repository, engine=engine)  # type: ignore[arg-type]

        job, cache_state, status_code = await service.run_analysis(
            AnalyzeRequest(query="omega-3 cardiovascular"),
            ProviderContext(provider="mock"),
        )
        assert cache_state is None
        assert status_code == 202
        assert job.status == JobStatus.pending
        assert job.id in service._active_tasks  # noqa: SLF001 - test-only visibility

        await asyncio.wait_for(engine.started.wait(), timeout=1.0)
        service._active_tasks[job.id].cancel()  # noqa: SLF001 - test-only cleanup
        try:
            await service._active_tasks[job.id]  # noqa: SLF001 - test-only cleanup
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
