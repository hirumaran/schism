from __future__ import annotations

import asyncio
from itertools import combinations

from app.config import Settings
from app.models.api import AnalyzeRequest
from app.models.claim import PaperClaim
from app.models.contradiction import ContradictionPair, build_pair_key
from app.models.paper import Paper, normalize_text
from app.models.report import AnalysisReport, ClaimCluster, SearchRun
from app.repositories.sqlite import SQLiteRepository
from app.services.embedding import EmbeddingService, cosine_similarity
from app.services.ingestion.service import IngestionService
from app.services.llm_client import LLMClient, ProviderContext
from app.services.vector_store import VectorStore


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

    async def analyze(self, request: AnalyzeRequest, context: ProviderContext) -> AnalysisReport:
        papers, search_run, warnings = await self._resolve_papers(request)
        if not papers:
            report = AnalysisReport(
                search_run_id=search_run.id if search_run else None,
                query=request.query,
                provider=context.normalized_provider,
                model=context.model,
                contradiction_threshold=request.contradiction_threshold,
                warnings=[*warnings, "No papers were available for analysis."],
            )
            self.repository.save_report(report)
            return report

        provider = context.normalized_provider
        self.repository.upsert_papers(papers)
        claims = await self._extract_claims(papers, provider, context)

        eligible_claims = [
            claim for claim in claims if claim.claim.strip() and claim.quality >= request.min_claim_quality
        ]
        if len(eligible_claims) < 2:
            report = AnalysisReport(
                search_run_id=search_run.id if search_run else None,
                query=request.query,
                provider=provider,
                model=context.model,
                contradiction_threshold=request.contradiction_threshold,
                papers=papers,
                claims=claims,
                warnings=[*warnings, "Not enough high-quality claims were extracted for contradiction analysis."],
            )
            self.repository.save_report(report)
            return report

        embeddings = self.embedding_service.embed_texts([claim.claim for claim in eligible_claims])
        self.vector_store.upsert_claims(eligible_claims, embeddings)
        clusters = self._cluster_claims(eligible_claims, embeddings, request.cluster_similarity_threshold)
        contradictions = await self._score_clusters(
            request=request,
            context=context,
            papers=papers,
            claims=eligible_claims,
            clusters=clusters,
        )
        contradictions = sorted(contradictions, key=lambda item: item.score, reverse=True)

        report = AnalysisReport(
            search_run_id=search_run.id if search_run else None,
            query=request.query,
            provider=provider,
            model=context.model,
            contradiction_threshold=request.contradiction_threshold,
            papers=papers,
            claims=claims,
            clusters=clusters,
            contradictions=contradictions,
            warnings=warnings,
        )
        self.repository.save_report(report)
        return report

    async def _resolve_papers(self, request: AnalyzeRequest) -> tuple[list[Paper], SearchRun | None, list[str]]:
        warnings: list[str] = []
        if request.paper_ids:
            papers = self.repository.get_papers(request.paper_ids)
            missing_ids = [paper_id for paper_id in request.paper_ids if paper_id not in {paper.id for paper in papers}]
            if missing_ids:
                warnings.append(f"{len(missing_ids)} paper ids were not found in local storage.")
            return papers, None, warnings

        ingestion_result = await self.ingestion_service.search(
            query=request.query or "",
            sources=request.sources,
            max_results=request.max_results,
        )
        papers = ingestion_result.papers
        search_run = SearchRun(
            query=request.query or "",
            sources=request.sources,
            max_results=request.max_results,
            total_papers=len(papers),
            warnings=ingestion_result.warnings,
        )
        self.repository.save_search_run(search_run, papers)
        return papers, search_run, ingestion_result.warnings

    async def _extract_claims(
        self, papers: list[Paper], provider: str, context: ProviderContext
    ) -> list[PaperClaim]:
        cached = self.repository.get_claims([paper.id for paper in papers], provider, context.model)
        fresh_claims: list[PaperClaim] = []
        semaphore = asyncio.Semaphore(max(1, self.settings.claim_concurrency))

        async def build_claim(paper: Paper) -> PaperClaim:
            existing = cached.get(paper.id)
            if existing is not None:
                return existing
            async with semaphore:
                claim = await self.llm_client.extract_claim(paper, context)
                fresh_claims.append(claim)
                return claim

        claims = await asyncio.gather(*(build_claim(paper) for paper in papers))
        self.repository.save_claims(fresh_claims)
        return list(claims)

    def _cluster_claims(
        self,
        claims: list[PaperClaim],
        embeddings: list[list[float]],
        similarity_threshold: float,
    ) -> list[ClaimCluster]:
        hdbscan_clusters = self._cluster_with_hdbscan(claims, embeddings)
        if hdbscan_clusters:
            return hdbscan_clusters

        adjacency = {index: set() for index in range(len(claims))}
        for left, right in combinations(range(len(claims)), 2):
            similarity = cosine_similarity(embeddings[left], embeddings[right])
            if similarity >= similarity_threshold:
                adjacency[left].add(right)
                adjacency[right].add(left)

        clusters: list[ClaimCluster] = []
        visited: set[int] = set()
        for start in range(len(claims)):
            if start in visited or not adjacency[start]:
                continue
            stack = [start]
            component: list[int] = []
            while stack:
                index = stack.pop()
                if index in visited:
                    continue
                visited.add(index)
                component.append(index)
                stack.extend(adjacency[index] - visited)

            component.sort()
            if len(component) < 2:
                continue
            clusters.append(
                ClaimCluster(
                    id=f"cluster_{len(clusters) + 1}",
                    paper_ids=[claims[index].paper_id for index in component],
                    claim_texts=[claims[index].claim for index in component],
                    average_similarity=self._average_similarity(component, embeddings),
                )
            )
        return clusters

    def _cluster_with_hdbscan(
        self, claims: list[PaperClaim], embeddings: list[list[float]]
    ) -> list[ClaimCluster]:
        if len(claims) < 2:
            return []
        try:
            import hdbscan
            import numpy as np
        except Exception:
            return []

        labels = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1).fit_predict(np.array(embeddings))
        grouped: dict[int, list[int]] = {}
        for index, label in enumerate(labels):
            if label < 0:
                continue
            grouped.setdefault(int(label), []).append(index)

        clusters: list[ClaimCluster] = []
        for label, indexes in grouped.items():
            if len(indexes) < 2:
                continue
            clusters.append(
                ClaimCluster(
                    id=f"cluster_{label}",
                    paper_ids=[claims[index].paper_id for index in indexes],
                    claim_texts=[claims[index].claim for index in indexes],
                    average_similarity=self._average_similarity(indexes, embeddings),
                )
            )
        return clusters

    async def _score_clusters(
        self,
        request: AnalyzeRequest,
        context: ProviderContext,
        papers: list[Paper],
        claims: list[PaperClaim],
        clusters: list[ClaimCluster],
    ) -> list[ContradictionPair]:
        paper_lookup = {paper.id: paper for paper in papers}
        claim_lookup = {claim.paper_id: claim for claim in claims}
        semaphore = asyncio.Semaphore(max(1, self.settings.scoring_concurrency))
        fresh_cache_entries: list[tuple[str, ContradictionPair]] = []

        async def score_pair(cluster_id: str, claim_a: PaperClaim, claim_b: PaperClaim) -> ContradictionPair | None:
            paper_a = paper_lookup[claim_a.paper_id]
            paper_b = paper_lookup[claim_b.paper_id]
            if not self._passes_overlap_filter(paper_a, paper_b, request.min_keyword_overlap):
                return None

            pair_key = build_pair_key(claim_a.claim, claim_b.claim, paper_a.id, paper_b.id)
            cached = self.repository.get_cached_contradiction(pair_key, context.normalized_provider, context.model)
            if cached is not None:
                return cached.model_copy(update={"cluster_id": cluster_id})

            async with semaphore:
                contradiction = await self.llm_client.score_contradiction(
                    claim_a=claim_a,
                    claim_b=claim_b,
                    paper_a=paper_a,
                    paper_b=paper_b,
                    context=context,
                )
            contradiction.cluster_id = cluster_id
            fresh_cache_entries.append((pair_key, contradiction))
            return contradiction

        tasks = []
        for cluster in clusters:
            cluster_claims = [claim_lookup[paper_id] for paper_id in cluster.paper_ids if paper_id in claim_lookup]
            for claim_a, claim_b in combinations(cluster_claims, 2):
                tasks.append(score_pair(cluster.id, claim_a, claim_b))

        scored = [item for item in await asyncio.gather(*tasks) if item is not None]
        for pair_key, contradiction in fresh_cache_entries:
            self.repository.save_cached_contradiction(pair_key, context.normalized_provider, context.model, contradiction)

        return [
            contradiction
            for contradiction in scored
            if contradiction.is_contradiction and contradiction.score >= request.contradiction_threshold
        ]

    @staticmethod
    def _average_similarity(indexes: list[int], embeddings: list[list[float]]) -> float | None:
        comparisons = [
            cosine_similarity(embeddings[left], embeddings[right])
            for left, right in combinations(indexes, 2)
        ]
        if not comparisons:
            return None
        return round(sum(comparisons) / len(comparisons), 4)

    @staticmethod
    def _passes_overlap_filter(paper_a: Paper, paper_b: Paper, min_keyword_overlap: int) -> bool:
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

        return len(paper_a.topic_tokens() & paper_b.topic_tokens()) >= min_keyword_overlap

