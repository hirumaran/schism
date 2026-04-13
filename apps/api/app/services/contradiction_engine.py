from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from itertools import combinations

from app.config import Settings
from app.logging_utils import StageTimer
from app.models.api import AnalyzeRequest
from app.models.claim import ClaimDirection, InputClaim, PaperClaim
from app.models.contradiction import (
    ContradictionMode,
    ContradictionPair,
    ContradictionType,
)
from app.models.paper import Paper, jaccard_similarity, normalize_text, tokenize_text
from app.models.report import (
    AnalysisJob,
    AnalysisReport,
    ClaimCluster,
    InputPaperMetadata,
    JobStatus,
    SearchRun,
)
from app.repositories.sqlite import SQLiteRepository
from app.services.embedding import EmbeddingService, cosine_similarity
from app.services.ingestion.service import IngestionResult, IngestionService
from app.services.llm_client import LLMClient, ProviderContext
from app.services.paper_input import ExtractedSections, ParsedInput
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

INCOMPATIBLE_POPULATIONS = [
    ("animal", "human"),
    ("in vitro", "human"),
    ("in vitro", "animal"),
    ("pediatric", "elderly"),
    ("healthy", "patient"),
]


class JobAbortedError(RuntimeError):
    """Raised when a job is cancelled or timed out."""


class ContradictionEngine:
    def __init__(
        self,
        settings: Settings,
        repository: SQLiteRepository,
        ingestion_service: IngestionService,
        llm_client: LLMClient,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.ingestion_service = ingestion_service
        self.llm_client = llm_client
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def analyze(
        self,
        request: AnalyzeRequest,
        context: ProviderContext,
        job: AnalysisJob | None = None,
    ) -> AnalysisReport:
        analysis_job = job or AnalysisJob(
            query=request.query or ",".join(request.paper_ids),
            mode=ContradictionMode.corpus_vs_corpus,
            provider=context.normalized_provider,
            model=context.model,
            status=JobStatus.pending,
            progress=5,
        )
        self.repository.create_job(analysis_job)
        await self._update_job(analysis_job, progress=5, status=JobStatus.pending)

        warnings: list[str] = []
        search_run: SearchRun | None = None
        try:
            await self._check_job_active(analysis_job.id)
            await self._update_job(
                analysis_job, progress=10, status=JobStatus.ingesting
            )
            async with StageTimer("ingestion", logger):
                papers, search_run, ingestion_result = await self._resolve_papers(
                    request
                )
            warnings.extend(ingestion_result.warnings)
            await self._update_job(
                analysis_job,
                progress=25,
                paper_count=len(papers),
                metadata={
                    **analysis_job.metadata,
                    "dedup_removed": ingestion_result.dedup_removed,
                    "filter_removed": ingestion_result.filter_removed,
                    "filtered_per_source": ingestion_result.filtered_per_source,
                    "sources_searched": ingestion_result.sources_searched,
                    "ingestion_cache_hits": ingestion_result.cache_hits,
                },
            )

            if not papers:
                report = self._empty_report(
                    job=analysis_job,
                    request=request,
                    context=context,
                    search_run=search_run,
                    warnings=[*warnings, "No papers were available for analysis."],
                )
                await self._complete_job(analysis_job, report, has_contradictions=False)
                return report

            self.repository.upsert_papers(papers)
            self.repository.link_job_papers(
                analysis_job.id, [paper.id for paper in papers]
            )

            await self._update_job(
                analysis_job, progress=35, status=JobStatus.embedding
            )
            async with StageTimer("embedding", logger):
                embeddings = await self._embed_papers_with_cache(papers, context)
            await self._update_job(analysis_job, progress=50)

            await self._check_job_active(analysis_job.id)
            await self._update_job(
                analysis_job, progress=55, status=JobStatus.analyzing
            )
            async with StageTimer("claim_extraction", logger):
                claims = await self._extract_claims(papers, context)
            skipped_reasons = self._skipped_claim_reasons(claims)
            extracted_claim_count = sum(1 for claim in claims if claim.claim)
            skipped_claim_count = sum(1 for claim in claims if not claim.claim)
            await self._update_job(
                analysis_job,
                progress=70,
                extracted_claim_count=extracted_claim_count,
                skipped_claim_count=skipped_claim_count,
                metadata={
                    **analysis_job.metadata,
                    "skipped_claim_reasons": skipped_reasons,
                },
            )
            self._apply_failover_meta(analysis_job, context)

            eligible_claims = [
                claim
                for claim in claims
                if claim.claim
                and not claim.discarded
                and claim.quality >= request.min_claim_quality
            ]
            if len(eligible_claims) < 2:
                report = AnalysisReport(
                    id=analysis_job.id,
                    job_id=analysis_job.id,
                    search_run_id=search_run.id if search_run else None,
                    query=request.query,
                    mode=ContradictionMode.corpus_vs_corpus,
                    provider=context.normalized_provider,
                    model=context.model,
                    status=JobStatus.done,
                    contradiction_threshold=request.contradiction_threshold,
                    papers=papers,
                    claims=claims,
                    warnings=[
                        *warnings,
                        "Not enough high-quality claims were extracted for contradiction analysis.",
                    ],
                    created_at=analysis_job.created_at,
                    completed_at=datetime.now(timezone.utc),
                )
                await self._complete_job(analysis_job, report, has_contradictions=False)
                return report

            async with StageTimer("clustering", logger):
                clusters = self._cluster_papers(papers, embeddings)
            cluster_metadata = [cluster.model_dump(mode="json") for cluster in clusters]
            await self._update_job(
                analysis_job,
                progress=75,
                cluster_count=len(clusters),
                metadata={
                    **analysis_job.metadata,
                    "cluster_metadata": cluster_metadata,
                },
            )

            await self._check_job_active(analysis_job.id)
            await self._update_job(analysis_job, progress=80)
            async with StageTimer("contradiction_scoring", logger):
                (
                    contradictions,
                    methodological,
                    score_summary,
                ) = await self._score_clusters(
                    job=analysis_job,
                    request=request,
                    context=context,
                    papers=papers,
                    claims=eligible_claims,
                    clusters=clusters,
                )

            contradictions = sorted(
                contradictions, key=lambda item: item.score, reverse=True
            )
            methodological = sorted(
                methodological, key=lambda item: item.raw_score, reverse=True
            )
            has_contradictions = score_summary["max_score"] >= 0.6 and bool(
                contradictions
            )
            metadata = {
                **analysis_job.metadata,
                "has_contradictions": has_contradictions,
                "max_pair_score": score_summary["max_score"],
                "total_eligible_pairs": score_summary["eligible_pairs"],
                "cache_hit_rate": score_summary["cache_hit_rate"],
            }
            await self._update_job(
                analysis_job,
                progress=95,
                contradiction_count=len(contradictions),
                filtered_pair_count=score_summary["filtered_pairs"],
                scored_pair_count=score_summary["llm_scored_pairs"],
                metadata=metadata,
                cached_pair_count=score_summary["cached_pairs"],
                has_contradictions=has_contradictions,
            )
            self._apply_failover_meta(analysis_job, context)

            report = AnalysisReport(
                id=analysis_job.id,
                job_id=analysis_job.id,
                search_run_id=search_run.id if search_run else None,
                query=request.query,
                mode=ContradictionMode.corpus_vs_corpus,
                provider=context.normalized_provider,
                model=context.model,
                status=JobStatus.done,
                contradiction_threshold=request.contradiction_threshold,
                has_contradictions=has_contradictions,
                papers=papers,
                claims=claims,
                clusters=clusters,
                contradictions=contradictions,
                methodological_differences=methodological,
                warnings=warnings,
                metadata=metadata,
                created_at=analysis_job.created_at,
                completed_at=datetime.now(timezone.utc),
            )
            await self._complete_job(
                analysis_job, report, has_contradictions=has_contradictions
            )
            return report
        except JobAbortedError as exc:
            job_state = self.repository.get_job(analysis_job.id) or analysis_job
            report = self._empty_report(
                job=job_state,
                request=request,
                context=context,
                search_run=search_run,
                warnings=[*warnings, str(exc)],
            )
            status = (
                job_state.status
                if job_state.status in {JobStatus.cancelled, JobStatus.failed}
                else JobStatus.cancelled
            )
            report.status = status
            job_state.status = status
            job_state.error = str(exc)
            job_state.completed_at = datetime.now(timezone.utc)
            self.repository.update_job(job_state)
            self.repository.save_report(report)
            raise
        except JobAbortedError as exc:
            job_state = self.repository.get_job(analysis_job.id) or analysis_job
            report = self._empty_report(
                job=job_state,
                request=None,
                context=context,
                search_run=search_run,
                warnings=[*warnings, str(exc)],
                mode=ContradictionMode.paper_vs_corpus,
                input_paper=InputPaperMetadata(
                    title=parsed_input.title
                    or parsed_input.filename
                    or "User-provided paper",
                    filename=parsed_input.filename,
                ),
            )
            report.status = job_state.status
            job_state.error = str(exc)
            job_state.completed_at = datetime.now(timezone.utc)
            self.repository.update_job(job_state)
            self.repository.save_report(report)
            raise
        except Exception as exc:
            analysis_job.status = JobStatus.failed
            analysis_job.error = str(exc)
            analysis_job.completed_at = datetime.now(timezone.utc)
            self.repository.update_job(analysis_job)
            logger.exception("analysis_failed")
            raise

    async def analyze_paper(
        self,
        *,
        parsed_input: ParsedInput,
        sections: ExtractedSections,
        max_results: int,
        sources: list[str],
        context: ProviderContext,
        job: AnalysisJob | None = None,
    ) -> AnalysisReport:
        analysis_job = job or AnalysisJob(
            query=parsed_input.title or parsed_input.filename or "User-provided paper",
            mode=ContradictionMode.paper_vs_corpus,
            provider=context.normalized_provider,
            model=context.model,
            status=JobStatus.pending,
            progress=5,
        )
        self.repository.create_job(analysis_job)
        await self._update_job(analysis_job, progress=5, status=JobStatus.pending)

        warnings: list[str] = []
        search_run: SearchRun | None = None
        try:
            await self._check_job_active(analysis_job.id)
            input_claims = await self.llm_client.extract_input_claims(
                sections.best_section, context
            )
            input_paper = self._build_input_paper(
                analysis_job.id, parsed_input, sections, input_claims
            )
            input_paper_metadata = InputPaperMetadata(
                title=input_paper.title,
                filename=parsed_input.filename,
                claims_extracted=len(input_claims),
                search_queries_used=[claim.search_query for claim in input_claims],
            )
            await self._update_job(
                analysis_job,
                progress=10,
                status=JobStatus.ingesting,
                metadata={
                    **analysis_job.metadata,
                    "input_paper": input_paper_metadata.model_dump(mode="json"),
                },
            )
            self._apply_failover_meta(analysis_job, context)

            async with StageTimer("ingestion", logger):
                (
                    papers,
                    search_run,
                    ingestion_result,
                ) = await self._resolve_papers_from_input_claims(
                    job=analysis_job,
                    input_claims=input_claims,
                    sources=sources,
                    max_results=max_results,
                )
            warnings.extend(ingestion_result.warnings)
            self.repository.upsert_papers([input_paper, *papers])
            self.repository.link_job_papers(
                analysis_job.id, [input_paper.id, *[paper.id for paper in papers]]
            )
            await self._update_job(
                analysis_job,
                progress=25,
                paper_count=len(papers) + 1,
                metadata={
                    **analysis_job.metadata,
                    "dedup_removed": ingestion_result.dedup_removed,
                    "filter_removed": ingestion_result.filter_removed,
                    "filtered_per_source": ingestion_result.filtered_per_source,
                    "sources_searched": ingestion_result.sources_searched,
                    "ingestion_cache_hits": ingestion_result.cache_hits,
                    "input_paper": input_paper_metadata.model_dump(mode="json"),
                },
            )

            if not input_claims:
                report = self._empty_report(
                    job=analysis_job,
                    request=None,
                    context=context,
                    search_run=search_run,
                    warnings=[
                        *warnings,
                        "No searchable claims were extracted from the input paper.",
                    ],
                    mode=ContradictionMode.paper_vs_corpus,
                    input_paper=input_paper_metadata,
                )
                report.papers = [input_paper]
                await self._complete_job(analysis_job, report, has_contradictions=False)
                return report

            if not papers:
                await self._update_job(
                    analysis_job,
                    extracted_claim_count=len(input_claims),
                    skipped_claim_count=0,
                )
                report = self._empty_report(
                    job=analysis_job,
                    request=None,
                    context=context,
                    search_run=search_run,
                    warnings=[*warnings, "No papers were available for analysis."],
                    mode=ContradictionMode.paper_vs_corpus,
                    input_paper=input_paper_metadata,
                )
                report.papers = [input_paper]
                report.claims = self._input_claims_as_paper_claims(
                    input_paper.id, context, input_claims
                )
                await self._complete_job(analysis_job, report, has_contradictions=False)
                return report

            await self._update_job(
                analysis_job, progress=35, status=JobStatus.embedding
            )
            async with StageTimer("embedding", logger):
                embeddings = await self._embed_papers_with_cache(papers, context)
            await self._update_job(analysis_job, progress=50)

            await self._check_job_active(analysis_job.id)
            await self._update_job(
                analysis_job, progress=55, status=JobStatus.analyzing
            )
            async with StageTimer("claim_extraction", logger):
                claims = await self._extract_claims(papers, context)
            skipped_reasons = self._skipped_claim_reasons(claims)
            extracted_claim_count = sum(1 for claim in claims if claim.claim)
            skipped_claim_count = sum(1 for claim in claims if not claim.claim)
            await self._update_job(
                analysis_job,
                progress=70,
                extracted_claim_count=extracted_claim_count + len(input_claims),
                skipped_claim_count=skipped_claim_count,
                metadata={
                    **analysis_job.metadata,
                    "skipped_claim_reasons": skipped_reasons,
                },
            )
            self._apply_failover_meta(analysis_job, context)

            eligible_claims = [
                claim
                for claim in claims
                if claim.claim and not claim.discarded and claim.quality >= 0.3
            ]
            async with StageTimer("clustering", logger):
                clusters = self._cluster_papers(papers, embeddings)
            cluster_metadata = [cluster.model_dump(mode="json") for cluster in clusters]
            await self._update_job(
                analysis_job,
                progress=75,
                cluster_count=len(clusters),
                metadata={
                    **analysis_job.metadata,
                    "cluster_metadata": cluster_metadata,
                },
            )

            await self._check_job_active(analysis_job.id)
            await self._update_job(
                analysis_job, progress=80, status=JobStatus.analyzing
            )
            async with StageTimer("contradiction_scoring", logger):
                (
                    contradictions,
                    methodological,
                    score_summary,
                ) = await self._score_input_claims(
                    job=analysis_job,
                    context=context,
                    input_paper=input_paper,
                    input_claims=input_claims,
                    fetched_papers=papers,
                    fetched_claims=eligible_claims,
                    clusters=clusters,
                )

            contradictions = sorted(
                contradictions, key=lambda item: item.score, reverse=True
            )
            methodological = sorted(
                methodological, key=lambda item: item.raw_score, reverse=True
            )
            has_contradictions = (
                bool(contradictions) and score_summary["max_score"] >= 0.6
            )
            metadata = {
                **analysis_job.metadata,
                "has_contradictions": has_contradictions,
                "max_pair_score": score_summary["max_score"],
                "total_eligible_pairs": score_summary["eligible_pairs"],
                "cache_hit_rate": score_summary["cache_hit_rate"],
                "input_paper": input_paper_metadata.model_dump(mode="json"),
            }
            await self._update_job(
                analysis_job,
                progress=95,
                contradiction_count=len(contradictions),
                filtered_pair_count=score_summary["filtered_pairs"],
                scored_pair_count=score_summary["llm_scored_pairs"],
                metadata=metadata,
                cached_pair_count=score_summary["cached_pairs"],
                has_contradictions=has_contradictions,
            )
            self._apply_failover_meta(analysis_job, context)

            report = AnalysisReport(
                id=analysis_job.id,
                job_id=analysis_job.id,
                search_run_id=search_run.id if search_run else None,
                query=analysis_job.query,
                mode=ContradictionMode.paper_vs_corpus,
                provider=context.normalized_provider,
                model=context.model,
                status=JobStatus.done,
                contradiction_threshold=self.settings.contradiction_threshold,
                has_contradictions=has_contradictions,
                papers=[input_paper, *papers],
                claims=[
                    *self._input_claims_as_paper_claims(
                        input_paper.id, context, input_claims
                    ),
                    *claims,
                ],
                clusters=clusters,
                contradictions=contradictions,
                methodological_differences=methodological,
                warnings=warnings,
                metadata=metadata,
                input_paper=input_paper_metadata,
                created_at=analysis_job.created_at,
                completed_at=datetime.now(timezone.utc),
            )
            await self._complete_job(
                analysis_job, report, has_contradictions=has_contradictions
            )
            return report
        except Exception as exc:
            analysis_job.status = JobStatus.failed
            analysis_job.error = str(exc)
            analysis_job.completed_at = datetime.now(timezone.utc)
            self.repository.update_job(analysis_job)
            logger.exception("paper_analysis_failed")
            raise

    async def _resolve_papers(
        self, request: AnalyzeRequest
    ) -> tuple[list[Paper], SearchRun | None, IngestionResult]:
        warnings: list[str] = []
        if request.paper_ids:
            papers = self.repository.get_papers(request.paper_ids)
            missing_ids = [
                paper_id
                for paper_id in request.paper_ids
                if paper_id not in {paper.id for paper in papers}
            ]
            if missing_ids:
                warnings.append(
                    f"{len(missing_ids)} paper ids were not found in local storage."
                )
            return papers, None, IngestionResult(papers=papers, warnings=warnings)

        ingestion_result = await self.ingestion_service.search(
            query=request.query or "",
            sources=request.sources,
            max_results=request.max_results,
        )
        search_run = SearchRun(
            query=request.query or "",
            sources=request.sources,
            max_results=request.max_results,
            total_papers=len(ingestion_result.papers),
            dedup_removed=ingestion_result.dedup_removed,
            filter_removed=ingestion_result.filter_removed,
            warnings=ingestion_result.warnings,
        )
        self.repository.save_search_run(search_run, ingestion_result.papers)
        return ingestion_result.papers, search_run, ingestion_result

    async def _resolve_papers_from_input_claims(
        self,
        *,
        job: AnalysisJob,
        input_claims: list[InputClaim],
        sources: list[str],
        max_results: int,
    ) -> tuple[list[Paper], SearchRun | None, IngestionResult]:
        if not input_claims:
            return [], None, IngestionResult(papers=[], warnings=[])

        results = await asyncio.gather(
            *[
                self.ingestion_service.search(
                    query=input_claim.search_query,
                    sources=sources,
                    max_results=max_results,
                )
                for input_claim in input_claims
            ]
        )

        aggregated_papers: list[Paper] = []
        warnings: list[str] = []
        filtered_per_source: dict[str, int] = {}
        sources_searched: set[str] = set()
        filter_removed = 0
        dedup_removed = 0
        cache_hits = 0
        for result in results:
            aggregated_papers.extend(result.papers)
            warnings.extend(result.warnings)
            filter_removed += result.filter_removed
            dedup_removed += result.dedup_removed
            cache_hits += result.cache_hits
            sources_searched.update(result.sources_searched)
            for source, count in result.filtered_per_source.items():
                filtered_per_source[source] = filtered_per_source.get(source, 0) + count

        deduped, cross_claim_dedup_removed = self.ingestion_service._dedupe(
            aggregated_papers
        )  # noqa: SLF001
        ranked = sorted(
            deduped,
            key=lambda paper: (
                (paper.citation_count or 0),
                (paper.influential_citation_count or 0),
                (paper.year or 0),
                len(paper.abstract or ""),
            ),
            reverse=True,
        )[:max_results]
        result = IngestionResult(
            papers=ranked,
            warnings=warnings,
            sources_searched=sorted(sources_searched),
            dedup_removed=dedup_removed + cross_claim_dedup_removed,
            filter_removed=filter_removed,
            filtered_per_source=filtered_per_source,
            cache_hits=cache_hits,
        )
        search_run = SearchRun(
            id=f"search_{job.id.removeprefix('job_')}",
            query=job.query,
            sources=sources,
            max_results=max_results,
            total_papers=len(ranked),
            dedup_removed=result.dedup_removed,
            filter_removed=result.filter_removed,
            warnings=result.warnings,
        )
        self.repository.save_search_run(search_run, ranked)
        return ranked, search_run, result

    async def _embed_papers_with_cache(
        self, papers: list[Paper], context: ProviderContext | None = None
    ) -> list[list[float]]:
        texts_to_embed: list[str] = []
        indexes_to_embed: list[int] = []
        embeddings: list[list[float] | None] = [None] * len(papers)

        for index, paper in enumerate(papers):
            vector = await self.vector_store.get_vector(paper.embedding_id)
            if vector is not None:
                embeddings[index] = vector
                continue
            indexes_to_embed.append(index)
            texts_to_embed.append(f"{paper.title}. {paper.abstract or ''}".strip())

        if texts_to_embed:
            provider = context.embedding_provider if context else "local"
            api_key = context.embedding_api_key if context else None
            new_vectors = await self.embedding_service.embed_texts(
                texts_to_embed, provider=provider, api_key=api_key
            )
            points = []
            for index, vector in zip(indexes_to_embed, new_vectors, strict=False):
                paper = papers[index]
                embeddings[index] = vector
                points.append(
                    {
                        "id": paper.embedding_id,
                        "vector": vector,
                        "payload": {
                            "paper_id": paper.id,
                            "title": paper.title,
                            "source": paper.source,
                        },
                    }
                )
            if new_vectors:
                await self.vector_store.upsert_embeddings(
                    points=points, dimensions=len(new_vectors[0])
                )

        return [vector or [] for vector in embeddings]

    async def _extract_claims(
        self, papers: list[Paper], context: ProviderContext
    ) -> list[PaperClaim]:
        cached = self.repository.get_best_claims([paper.id for paper in papers])
        fresh_claims: list[PaperClaim] = []
        concurrency = self._claim_concurrency(context)
        semaphore = asyncio.Semaphore(concurrency)

        async def build_claim(paper: Paper) -> PaperClaim:
            existing = cached.get(paper.id)
            if existing is not None and existing.claim:
                return existing
            async with semaphore:
                claim = await self.llm_client.extract_claim(paper, context)
                if claim.claim:
                    paper.magnitude = claim.magnitude.value if claim.magnitude else None
                    paper.population = claim.population
                    paper.outcome = claim.outcome
                fresh_claims.append(claim)
                return claim

        claims = await asyncio.gather(*(build_claim(paper) for paper in papers))
        self.repository.save_claims(fresh_claims)
        self.repository.upsert_papers(papers)
        return list(claims)

    def _build_input_paper(
        self,
        job_id: str,
        parsed_input: ParsedInput,
        sections: ExtractedSections,
        input_claims: list[InputClaim],
    ) -> Paper:
        primary_claim = input_claims[0] if input_claims else None
        title = parsed_input.title or parsed_input.filename or "User-provided paper"
        return Paper(
            id=f"input_{job_id}",
            source="user_input",
            external_id=job_id,
            title=title,
            abstract=sections.best_section[:2000],
            population=primary_claim.population if primary_claim else None,
            outcome=primary_claim.outcome if primary_claim else None,
            raw={
                "filename": parsed_input.filename,
                "input_claims": [
                    claim.model_dump(mode="json") for claim in input_claims
                ],
            },
        )

    @staticmethod
    def _input_claims_as_paper_claims(
        paper_id: str,
        context: ProviderContext,
        input_claims: list[InputClaim],
    ) -> list[PaperClaim]:
        return [
            PaperClaim(
                paper_id=paper_id,
                provider=context.normalized_provider,
                model=context.model,
                found=True,
                claim=claim.claim,
                direction=claim.direction,
                population=claim.population,
                outcome=claim.outcome,
                confidence=1.0,
                quality=1.0,
                raw={"search_query": claim.search_query, "mode": "input_paper"},
            )
            for claim in input_claims
        ]

    def _claim_concurrency(self, context: ProviderContext) -> int:
        provider = context.normalized_provider
        if provider == "openai":
            return max(1, self.settings.openai_claim_concurrency)
        if provider == "anthropic":
            return max(1, self.settings.anthropic_claim_concurrency)
        return max(1, self.settings.claim_concurrency)

    def _cluster_papers(
        self, papers: list[Paper], embeddings: list[list[float]]
    ) -> list[ClaimCluster]:
        hdbscan_clusters = self._cluster_with_hdbscan(papers, embeddings)
        if len(hdbscan_clusters) <= 1:
            logger.info(
                "clustering_fallback_used", extra={"reason": "hdbscan_single_or_noise"}
            )
            return self._fallback_cluster_papers(papers, embeddings)
        return hdbscan_clusters

    def _cluster_with_hdbscan(
        self, papers: list[Paper], embeddings: list[list[float]]
    ) -> list[ClaimCluster]:
        if len(papers) < 2:
            return []
        try:
            import hdbscan
            import numpy as np
        except Exception:
            return []

        min_cluster_size = max(2, min(5, len(papers) // 8))
        labels = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size, min_samples=1
        ).fit_predict(np.array(embeddings))
        grouped: dict[int, list[int]] = {}
        for index, label in enumerate(labels):
            if label < 0:
                continue
            grouped.setdefault(int(label), []).append(index)

        clusters = [
            self._build_cluster(
                f"cluster_{label}", indexes, papers, embeddings, fallback_used=False
            )
            for label, indexes in grouped.items()
            if len(indexes) >= 2
        ]
        return [cluster for cluster in clusters if cluster.paper_count >= 2]

    def _fallback_cluster_papers(
        self, papers: list[Paper], embeddings: list[list[float]]
    ) -> list[ClaimCluster]:
        pair_scores = []
        for left, right in combinations(range(len(papers)), 2):
            similarity = cosine_similarity(embeddings[left], embeddings[right])
            if similarity > 0.65:
                pair_scores.append((similarity, left, right))
        pair_scores.sort(reverse=True)

        clusters: list[set[int]] = []
        for _, left, right in pair_scores:
            matching = [
                cluster for cluster in clusters if left in cluster or right in cluster
            ]
            if not matching:
                clusters.append({left, right})
                continue
            target = matching[0]
            target.update({left, right})
            for extra in matching[1:]:
                target.update(extra)
                clusters.remove(extra)

        built = [
            self._build_cluster(
                f"cluster_fallback_{idx + 1}",
                sorted(indexes),
                papers,
                embeddings,
                fallback_used=True,
            )
            for idx, indexes in enumerate(clusters)
            if len(indexes) >= 2
        ]
        if not built and len(papers) >= 2:
            built = [
                self._build_cluster(
                    "cluster_fallback_all",
                    list(range(len(papers))),
                    papers,
                    embeddings,
                    fallback_used=True,
                )
            ]
        return [cluster for cluster in built if cluster.paper_count >= 2]

    def _build_cluster(
        self,
        cluster_id: str,
        indexes: list[int],
        papers: list[Paper],
        embeddings: list[list[float]],
        *,
        fallback_used: bool,
    ) -> ClaimCluster:
        selected = [papers[index] for index in indexes]
        trimmed_count = 0
        if len(selected) > 20:
            selected = sorted(
                selected, key=lambda paper: paper.citation_count or 0, reverse=True
            )[:20]
            trimmed_count = len(indexes) - len(selected)
            logger.info(
                "cluster_trimmed",
                extra={"cluster_id": cluster_id, "trimmed_count": trimmed_count},
            )

        cluster_indexes = [papers.index(paper) for paper in selected]
        years = [paper.year for paper in selected if paper.year is not None]
        return ClaimCluster(
            id=cluster_id,
            paper_ids=[paper.id for paper in selected],
            claim_texts=[paper.title for paper in selected],
            average_similarity=self._average_similarity(cluster_indexes, embeddings),
            paper_count=len(selected),
            avg_year=round(sum(years) / len(years), 1) if years else None,
            year_range=[min(years), max(years)] if years else [],
            top_terms=self._top_terms(selected),
            trimmed_count=trimmed_count,
            fallback_used=fallback_used,
        )

    async def _score_clusters(
        self,
        job: AnalysisJob,
        request: AnalyzeRequest,
        context: ProviderContext,
        papers: list[Paper],
        claims: list[PaperClaim],
        clusters: list[ClaimCluster],
    ) -> tuple[
        list[ContradictionPair], list[ContradictionPair], dict[str, float | int]
    ]:
        paper_lookup = {paper.id: paper for paper in papers}
        claim_lookup = {claim.paper_id: claim for claim in claims}
        semaphore = asyncio.Semaphore(max(1, self.settings.scoring_concurrency))
        contradictions: list[ContradictionPair] = []
        methodological: list[ContradictionPair] = []
        best_pairs: dict[str, ContradictionPair] = {}
        filtered_pairs = 0
        llm_scored_pairs = 0
        cached_pairs = 0
        eligible_pairs = 0

        async def score_pair(
            cluster_id: str, claim_a: PaperClaim, claim_b: PaperClaim
        ) -> ContradictionPair | None:
            nonlocal filtered_pairs, llm_scored_pairs, cached_pairs, eligible_pairs
            paper_a = paper_lookup[claim_a.paper_id]
            paper_b = paper_lookup[claim_b.paper_id]
            filter_result = self._prefilter_pair(
                claim_a, claim_b, paper_a, paper_b, request.min_keyword_overlap
            )
            if filter_result["action"] == "skip":
                filtered_pairs += 1
                return None
            if filter_result["action"] == "methodological":
                eligible_pairs += 1
                pair = filter_result["pair"]
                pair.cluster_id = cluster_id
                return pair

            eligible_pairs += 1
            cached = self.repository.get_cached_contradiction(paper_a.id, paper_b.id)
            if cached is not None:
                cached_pairs += 1
                cached.cluster_id = cluster_id
                return self._apply_year_penalty(cached, paper_a, paper_b)

            async with semaphore:
                llm_scored_pairs += 1
                contradiction = await self.llm_client.score_contradiction(
                    claim_a=claim_a,
                    claim_b=claim_b,
                    paper_a=paper_a,
                    paper_b=paper_b,
                    context=context,
                )
            contradiction.cluster_id = cluster_id
            contradiction = self._apply_year_penalty(contradiction, paper_a, paper_b)
            return contradiction

        tasks = []
        for cluster in clusters:
            cluster_claims = [
                claim_lookup[paper_id]
                for paper_id in cluster.paper_ids
                if paper_id in claim_lookup
            ]
            for claim_a, claim_b in combinations(cluster_claims, 2):
                tasks.append(score_pair(cluster.id, claim_a, claim_b))

        for item in [pair for pair in await asyncio.gather(*tasks) if pair is not None]:
            existing = best_pairs.get(item.pair_key or "")
            if existing is None or item.score > existing.score:
                best_pairs[item.pair_key or ""] = item

        saved_count = 0
        for item in best_pairs.values():
            if (
                item.type == ContradictionType.methodological
                and item.score < request.contradiction_threshold
            ):
                methodological.append(item)
                if self.repository.save_contradiction(
                    item, job_id=job.id, kind="methodological"
                ):
                    saved_count += 1
                continue
            if item.is_contradiction and item.score >= request.contradiction_threshold:
                contradictions.append(item)
                if self.repository.save_contradiction(item, job_id=job.id):
                    saved_count += 1

        max_score = max(
            [pair.score for pair in [*contradictions, *methodological]], default=0.0
        )
        cache_denominator = eligible_pairs if eligible_pairs else 1
        return (
            contradictions,
            methodological,
            {
                "max_score": max_score,
                "filtered_pairs": filtered_pairs,
                "llm_scored_pairs": llm_scored_pairs,
                "cached_pairs": cached_pairs,
                "eligible_pairs": eligible_pairs,
                "cache_hit_rate": round(cached_pairs / cache_denominator, 4)
                if eligible_pairs
                else 0.0,
            },
        )

    async def _score_input_claims(
        self,
        *,
        job: AnalysisJob,
        context: ProviderContext,
        input_paper: Paper,
        input_claims: list[InputClaim],
        fetched_papers: list[Paper],
        fetched_claims: list[PaperClaim],
        clusters: list[ClaimCluster],
    ) -> tuple[
        list[ContradictionPair], list[ContradictionPair], dict[str, float | int]
    ]:
        paper_lookup = {paper.id: paper for paper in fetched_papers}
        cluster_lookup = {
            paper_id: cluster.id
            for cluster in clusters
            for paper_id in cluster.paper_ids
        }
        semaphore = asyncio.Semaphore(max(1, self.settings.scoring_concurrency))
        best_pairs: dict[str, ContradictionPair] = {}
        filtered_pairs = 0
        llm_scored_pairs = 0
        eligible_pairs = 0

        async def score_pair(
            input_claim: InputClaim, fetched_claim: PaperClaim
        ) -> ContradictionPair | None:
            nonlocal filtered_pairs, llm_scored_pairs, eligible_pairs
            paper_b = paper_lookup[fetched_claim.paper_id]
            filter_result = self._prefilter_input_pair(
                input_claim, fetched_claim, input_paper, paper_b
            )
            if filter_result["action"] == "skip":
                filtered_pairs += 1
                return None

            eligible_pairs += 1
            if filter_result["action"] == "methodological":
                pair = filter_result["pair"]
            else:
                input_paper_claim = PaperClaim(
                    paper_id=input_paper.id,
                    provider=context.normalized_provider,
                    model=context.model,
                    found=True,
                    claim=input_claim.claim,
                    direction=input_claim.direction,
                    population=input_claim.population,
                    outcome=input_claim.outcome,
                    confidence=1.0,
                    quality=1.0,
                    raw={
                        "search_query": input_claim.search_query,
                        "mode": "input_paper",
                    },
                )
                async with semaphore:
                    llm_scored_pairs += 1
                    pair = await self.llm_client.score_contradiction(
                        claim_a=input_paper_claim,
                        claim_b=fetched_claim,
                        paper_a=input_paper,
                        paper_b=paper_b,
                        context=context,
                    )

            pair.mode = ContradictionMode.paper_vs_corpus
            pair.paper_a_id = input_paper.id
            pair.paper_b_id = paper_b.id
            pair.paper_a_claim = input_claim.claim
            pair.paper_b_claim = fetched_claim.claim
            pair.cluster_id = cluster_lookup.get(paper_b.id)
            return self._apply_year_penalty(pair, input_paper, paper_b)

        tasks = [
            score_pair(input_claim, fetched_claim)
            for fetched_claim in fetched_claims
            for input_claim in input_claims
        ]
        for pair in [item for item in await asyncio.gather(*tasks) if item is not None]:
            existing = best_pairs.get(pair.pair_key or "")
            if existing is None or pair.score > existing.score:
                best_pairs[pair.pair_key or ""] = pair

        contradictions: list[ContradictionPair] = []
        methodological: list[ContradictionPair] = []
        for pair in best_pairs.values():
            if (
                pair.type == ContradictionType.methodological
                and pair.score < self.settings.contradiction_threshold
            ):
                methodological.append(pair)
                self.repository.save_contradiction(
                    pair, job_id=job.id, kind="methodological"
                )
                continue
            if (
                pair.is_contradiction
                and pair.score >= self.settings.contradiction_threshold
            ):
                contradictions.append(pair)
                self.repository.save_contradiction(pair, job_id=job.id)

        max_score = max(
            [pair.score for pair in [*contradictions, *methodological]], default=0.0
        )
        return (
            contradictions,
            methodological,
            {
                "max_score": max_score,
                "filtered_pairs": filtered_pairs,
                "llm_scored_pairs": llm_scored_pairs,
                "cached_pairs": 0,
                "eligible_pairs": eligible_pairs,
                "cache_hit_rate": 0.0,
            },
        )

    def _prefilter_pair(
        self,
        claim_a: PaperClaim,
        claim_b: PaperClaim,
        paper_a: Paper,
        paper_b: Paper,
        min_keyword_overlap: int,
    ) -> dict[str, object]:
        if not self._passes_overlap_filter(paper_a, paper_b, min_keyword_overlap):
            return {"action": "skip"}

        outcome_a = claim_a.outcome or paper_a.outcome or ""
        outcome_b = claim_b.outcome or paper_b.outcome or ""
        if (
            claim_a.direction == claim_b.direction
            and outcome_a
            and outcome_b
            and normalize_text(outcome_a) == normalize_text(outcome_b)
        ):
            return {"action": "skip"}

        if (
            claim_a.direction != ClaimDirection.null
            and claim_b.direction != ClaimDirection.null
            and claim_a.direction == claim_b.direction
        ):
            return {"action": "skip"}

        outcome_similarity = jaccard_similarity(outcome_a, outcome_b)
        if outcome_similarity < 0.2:
            return {"action": "skip"}

        population_a = normalize_text(claim_a.population or paper_a.population or "")
        population_b = normalize_text(claim_b.population or paper_b.population or "")
        if (
            population_a
            and population_b
            and self._incompatible_populations(population_a, population_b)
        ):
            pair = ContradictionPair(
                paper_a_id=paper_a.id,
                paper_b_id=paper_b.id,
                mode=ContradictionMode.corpus_vs_corpus,
                provider="prefilter",
                model=None,
                raw_score=0.3,
                score=0.3,
                type=ContradictionType.methodological,
                explanation="The papers study incompatible populations, so the disagreement is methodological rather than contradictory.",
                is_contradiction=False,
                could_both_be_true=True,
                key_difference="population mismatch",
                paper_a_claim=claim_a.claim,
                paper_b_claim=claim_b.claim,
                raw={"mode": "prefilter"},
            )
            return {"action": "methodological", "pair": pair}

        if (
            claim_a.direction == claim_b.direction
            and claim_a.direction != ClaimDirection.null
        ):
            return {"action": "skip"}
        return {"action": "score"}

    def _prefilter_input_pair(
        self,
        input_claim: InputClaim,
        fetched_claim: PaperClaim,
        input_paper: Paper,
        fetched_paper: Paper,
    ) -> dict[str, object]:
        outcome_similarity = jaccard_similarity(
            input_claim.outcome, fetched_claim.outcome or fetched_paper.outcome
        )
        if outcome_similarity < 0.2:
            return {"action": "skip"}
        if input_claim.direction == fetched_claim.direction:
            return {"action": "skip"}

        population_a = normalize_text(
            input_claim.population or input_paper.population or ""
        )
        population_b = normalize_text(
            fetched_claim.population or fetched_paper.population or ""
        )
        if (
            population_a
            and population_b
            and self._incompatible_populations(population_a, population_b)
        ):
            pair = ContradictionPair(
                paper_a_id=input_paper.id,
                paper_b_id=fetched_paper.id,
                mode=ContradictionMode.paper_vs_corpus,
                provider="prefilter",
                raw_score=0.3,
                score=0.3,
                type=ContradictionType.methodological,
                explanation="The input claim and fetched paper study incompatible populations, so the difference is methodological.",
                is_contradiction=False,
                could_both_be_true=True,
                key_difference="population mismatch",
                paper_a_claim=input_claim.claim,
                paper_b_claim=fetched_claim.claim,
                raw={"mode": "prefilter"},
            )
            return {"action": "methodological", "pair": pair}
        return {"action": "score"}

    @staticmethod
    def _incompatible_populations(left: str, right: str) -> bool:
        return (left, right) in INCOMPATIBLE_POPULATIONS or (
            right,
            left,
        ) in INCOMPATIBLE_POPULATIONS

    @staticmethod
    def _apply_year_penalty(
        pair: ContradictionPair, paper_a: Paper, paper_b: Paper
    ) -> ContradictionPair:
        if paper_a.year is None or paper_b.year is None:
            pair.raw_score = pair.raw_score or pair.score
            return pair
        pair.raw_score = pair.raw_score or pair.score
        gap = abs(paper_a.year - paper_b.year)
        if gap > 15:
            pair.score_penalty = 0.15
            pair.score = max(0.0, pair.raw_score - 0.15)
        return pair

    @staticmethod
    def _average_similarity(
        indexes: list[int], embeddings: list[list[float]]
    ) -> float | None:
        comparisons = [
            cosine_similarity(embeddings[left], embeddings[right])
            for left, right in combinations(indexes, 2)
        ]
        if not comparisons:
            return None
        return round(sum(comparisons) / len(comparisons), 4)

    @staticmethod
    def _top_terms(papers: list[Paper]) -> list[str]:
        texts = [paper.abstract or paper.title for paper in papers]
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(max_features=5, stop_words="english")
            vectorizer.fit(texts)
            return list(vectorizer.get_feature_names_out())[:5]
        except Exception:
            tokens: dict[str, int] = {}
            for text in texts:
                for token in tokenize_text(text, drop_stop_words=True, min_length=3):
                    tokens[token] = tokens.get(token, 0) + 1
            return [
                term
                for term, _ in sorted(
                    tokens.items(), key=lambda item: item[1], reverse=True
                )[:5]
            ]

    async def _update_job(
        self,
        job: AnalysisJob,
        progress: int | None = None,
        status: JobStatus | None = None,
        **updates,
    ) -> None:
        if progress is not None:
            job.progress = progress
        if status is not None:
            job.status = status
        for key, value in updates.items():
            setattr(job, key, value)
        self.repository.update_job(job)

    async def _check_job_active(self, job_id: str) -> None:
        latest = self.repository.get_job(job_id)
        if latest is None:
            raise JobAbortedError("job_not_found")
        if latest.status == JobStatus.cancelled:
            raise JobAbortedError("job_cancelled")
        if latest.status == JobStatus.failed and latest.error == "job_timeout_exceeded":
            raise JobAbortedError("job_timeout_exceeded")

    def _apply_failover_meta(
        self, job: AnalysisJob, context: ProviderContext
    ) -> None:
        """Apply failover metadata from the ProviderContext to the AnalysisJob if any LLM call triggered failover."""
        if context.failover_meta is None:
            return
        if context.failover_meta.failover_occurred:
            job.failover_occurred = True
            job.provider_used = context.failover_meta.provider_used
            job.primary_error = context.failover_meta.primary_error
            self.repository.update_job(job)

    async def _complete_job(
        self, job: AnalysisJob, report: AnalysisReport, has_contradictions: bool
    ) -> None:
        job.status = JobStatus.done
        job.progress = 100
        job.has_contradictions = has_contradictions
        job.completed_at = datetime.now(timezone.utc)
        self.repository.update_job(job)
        report.status = JobStatus.done
        report.completed_at = job.completed_at
        self.repository.save_report(report)

    def _empty_report(
        self,
        job: AnalysisJob,
        request: AnalyzeRequest | None,
        context: ProviderContext,
        search_run: SearchRun | None,
        warnings: list[str],
        mode: ContradictionMode | None = None,
        input_paper: InputPaperMetadata | None = None,
    ) -> AnalysisReport:
        return AnalysisReport(
            id=job.id,
            job_id=job.id,
            search_run_id=search_run.id if search_run else None,
            query=request.query if request is not None else job.query,
            mode=mode or job.mode,
            provider=context.normalized_provider,
            model=context.model,
            status=job.status,
            contradiction_threshold=request.contradiction_threshold
            if request is not None
            else self.settings.contradiction_threshold,
            warnings=warnings,
            metadata=job.metadata,
            input_paper=input_paper,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def _passes_overlap_filter(
        paper_a: Paper, paper_b: Paper, min_keyword_overlap: int
    ) -> bool:
        if min_keyword_overlap <= 0:
            return True

        metadata_a = {
            token
            for value in [*paper_a.keywords, *paper_a.mesh_terms]
            for token in normalize_text(value).split()
            if len(token) > 2
        }
        metadata_b = {
            token
            for value in [*paper_b.keywords, *paper_b.mesh_terms]
            for token in normalize_text(value).split()
            if len(token) > 2
        }
        if metadata_a and metadata_b:
            return len(metadata_a & metadata_b) >= min_keyword_overlap

        return (
            len(paper_a.topic_tokens() & paper_b.topic_tokens()) >= min_keyword_overlap
        )

    @staticmethod
    def _skipped_claim_reasons(claims: list[PaperClaim]) -> dict[str, int]:
        reasons: dict[str, int] = {}
        for claim in claims:
            if claim.skip_reason:
                reasons[claim.skip_reason] = reasons.get(claim.skip_reason, 0) + 1
        return reasons
