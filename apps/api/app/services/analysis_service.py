from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import Settings
from app.logging_utils import bind_job_id
from app.models.api import AnalyzeRequest
from app.models.contradiction import ContradictionMode, ContradictionPair, ContradictionType
from app.models.paper import normalize_query
from app.models.report import AnalysisJob, JobStatus
from app.repositories.sqlite import ACTIVE_JOB_STATUSES, SQLiteRepository
from app.services.contradiction_engine import ContradictionEngine, JobAbortedError
from app.services.llm_client import ProviderContext
from app.services.paper_input import ExtractedSections, ParsedInput

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, settings: Settings, repository: SQLiteRepository, engine: ContradictionEngine) -> None:
        self.settings = settings
        self.repository = repository
        self.engine = engine
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._watchdog_task: asyncio.Task | None = None

    async def start_watchdog(self) -> None:
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def stop_watchdog(self) -> None:
        if self._watchdog_task is None:
            return
        self._watchdog_task.cancel()
        try:
            await self._watchdog_task
        except asyncio.CancelledError:
            pass
        self._watchdog_task = None

    async def run_analysis(self, request: AnalyzeRequest, context: ProviderContext) -> tuple[AnalysisJob, str | None, int]:
        query = request.query or ",".join(request.paper_ids)
        normalized = normalize_query(query)
        if request.query and not request.paper_ids:
            running_job = self.repository.get_recent_active_job(normalized, ContradictionMode.corpus_vs_corpus)
            if running_job is not None:
                return running_job, "IN_PROGRESS", 200
            cached_job = self.repository.get_recent_completed_job(
                normalized,
                within_hours=self.settings.analysis_cache_hours,
            )
            if cached_job is not None:
                return cached_job, "HIT", 200

        job = AnalysisJob(
            query=query,
            normalized_query=normalized,
            mode=ContradictionMode.corpus_vs_corpus,
            provider=context.normalized_provider,
            model=context.model,
            status=JobStatus.pending,
            progress=0,
        )
        self.repository.create_job(job)
        self._spawn_task(job.id, self.engine.analyze(request=request, context=context, job=job))
        return job, None, 202

    async def run_paper_analysis(
        self,
        *,
        parsed_input: ParsedInput,
        sections: ExtractedSections,
        max_results: int,
        sources: list[str],
        context: ProviderContext,
    ) -> tuple[AnalysisJob, str | None, int]:
        query = parsed_input.title or parsed_input.filename or "User-provided paper"
        job = AnalysisJob(
            query=query,
            normalized_query=normalize_query(query),
            mode=ContradictionMode.paper_vs_corpus,
            provider=context.normalized_provider,
            model=context.model,
            status=JobStatus.pending,
            progress=0,
            metadata={
                "input_filename": parsed_input.filename,
            },
        )
        self.repository.create_job(job)
        self._spawn_task(
            job.id,
            self.engine.analyze_paper(
                parsed_input=parsed_input,
                sections=sections,
                max_results=max_results,
                sources=sources,
                context=context,
                job=job,
            ),
        )
        return job, None, 202

    def get_job(self, job_id: str) -> AnalysisJob | None:
        return self.repository.get_job(job_id)

    def get_job_stats(self, job_id: str):
        return self.repository.get_job_stats(job_id)

    def get_job_results(
        self,
        job_id: str,
        *,
        contradiction_type: ContradictionType | None,
        mode: ContradictionMode | None,
        limit: int,
        offset: int,
    ) -> dict[str, object] | None:
        job = self.repository.get_job(job_id)
        if job is None:
            return None

        papers = self.repository.get_job_papers(job_id)
        paper_lookup = {paper.id: paper for paper in papers}
        report = self.repository.get_report(job_id)
        if report is not None:
            for paper in report.papers:
                paper_lookup[paper.id] = paper

        results = self.repository.list_job_contradictions(job_id, kind="contradiction")
        filtered: list[ContradictionPair] = []
        for pair in results:
            if not pair.is_contradiction or pair.score < self.settings.contradiction_threshold:
                continue
            if contradiction_type is not None and pair.type != contradiction_type:
                continue
            if mode is not None and pair.mode != mode:
                continue
            filtered.append(
                pair.model_copy(
                    update={
                        "paper_a": paper_lookup.get(pair.paper_a_id),
                        "paper_b": paper_lookup.get(pair.paper_b_id),
                    }
                )
            )

        filtered.sort(key=lambda item: item.score, reverse=True)
        sliced = filtered[offset : offset + limit]
        return {
            "job_id": job.id,
            "query": job.query,
            "total": len(filtered),
            "results": [item.model_dump(mode="json") for item in sliced],
        }

    async def cancel_or_delete_job(self, job_id: str) -> bool:
        job = self.repository.get_job(job_id)
        if job is None:
            return False
        if job.status in ACTIVE_JOB_STATUSES:
            job.status = JobStatus.cancelled
            job.completed_at = datetime.now(timezone.utc)
            self.repository.update_job(job)
            task = self._active_tasks.get(job_id)
            if task is not None:
                task.cancel()
            return True
        return self.repository.delete_job(job_id)

    def _spawn_task(self, job_id: str, coroutine) -> None:
        task = asyncio.create_task(self._run_job(job_id, coroutine))
        self._active_tasks[job_id] = task

        def cleanup(done_task: asyncio.Task) -> None:
            self._active_tasks.pop(job_id, None)
            try:
                done_task.result()
            except asyncio.CancelledError:
                logger.info("analysis_job_task_cancelled", extra={"job_id": job_id})
            except JobAbortedError:
                logger.info("analysis_job_task_aborted", extra={"job_id": job_id})
            except Exception:
                logger.exception("analysis_job_task_failed", extra={"job_id": job_id})

        task.add_done_callback(cleanup)

    async def _run_job(self, job_id: str, coroutine) -> None:
        with bind_job_id(job_id):
            try:
                await coroutine
            except JobAbortedError:
                logger.info("analysis_job_aborted")
                raise
            except asyncio.CancelledError:
                latest = self.repository.get_job(job_id)
                if latest is not None and latest.status == JobStatus.failed and latest.error == "job_timeout_exceeded":
                    logger.warning("analysis_job_timed_out")
                    raise
                if latest is not None:
                    latest.status = JobStatus.cancelled
                    latest.completed_at = datetime.now(timezone.utc)
                    self.repository.update_job(latest)
                logger.info("analysis_job_cancelled")
                raise

    async def _watchdog_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            expired = self.repository.expire_stale_running_jobs(self.settings.job_timeout_minutes)
            for job_id in expired:
                logger.warning("analysis_job_timed_out", extra={"job_id": job_id})
                task = self._active_tasks.get(job_id)
                if task is not None:
                    task.cancel()
