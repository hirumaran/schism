from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.config import Settings
from app.models.paper import Paper, normalize_title_for_dedupe, tokenize_text, word_count
from app.repositories.sqlite import SQLiteRepository
from app.services.ingestion.arxiv import ArxivClient
from app.services.ingestion.openalex import OpenAlexClient
from app.services.ingestion.pubmed import PubMedClient
from app.services.ingestion.semantic_scholar import SemanticScholarClient

logger = logging.getLogger(__name__)

try:
    from rapidfuzz.distance import Levenshtein
except Exception:  # pragma: no cover - fallback if dependency is absent
    Levenshtein = None


SOURCE_CAPS = {
    "arxiv": 40,
    "semantic_scholar": 40,
    "pubmed": 30,
    "openalex": 40,
}


@dataclass(slots=True)
class IngestionResult:
    papers: list[Paper]
    warnings: list[str]
    sources_searched: list[str] = field(default_factory=list)
    dedup_removed: int = 0
    filter_removed: int = 0
    filtered_per_source: dict[str, int] = field(default_factory=dict)
    cache_hits: int = 0


class IngestionService:
    def __init__(self, user_agent: str, contact_email: str | None, repository: SQLiteRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.clients = {
            "arxiv": ArxivClient(user_agent=user_agent),
            "semantic_scholar": SemanticScholarClient(),
            "openalex": OpenAlexClient(user_agent=user_agent, contact_email=contact_email),
            "pubmed": PubMedClient(user_agent=user_agent, contact_email=contact_email),
        }

    async def search(self, query: str, sources: list[str], max_results: int) -> IngestionResult:
        selected_sources = [source for source in sources if source in self.clients]
        if not selected_sources:
            return IngestionResult(papers=[], warnings=["No supported sources were requested."])

        tasks = {
            source: asyncio.create_task(self._fetch_source(source=source, query=query, max_results=max_results))
            for source in selected_sources
        }
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

        warnings: list[str] = []
        papers: list[Paper] = []
        filter_removed = 0
        filtered_per_source: dict[str, int] = {}
        cache_hits = 0

        for source, response in zip(tasks.keys(), responses, strict=False):
            if isinstance(response, Exception):
                warnings.append(f"{source} search failed: {response}")
                logger.warning("source_search_failed", extra={"source": source, "error": str(response)})
                continue

            papers.extend(response["papers"])
            filter_removed += response["filtered_count"]
            filtered_per_source[source] = response["filtered_count"]
            cache_hits += 1 if response["cache_hit"] else 0

        deduped, dedup_removed = self._dedupe(papers)
        ranked = sorted(
            deduped,
            key=lambda paper: (
                (paper.citation_count or 0),
                (paper.influential_citation_count or 0),
                (paper.year or 0),
                len(paper.abstract or ""),
            ),
            reverse=True,
        )

        return IngestionResult(
            papers=ranked[:max_results],
            warnings=warnings,
            sources_searched=selected_sources,
            dedup_removed=dedup_removed,
            filter_removed=filter_removed,
            filtered_per_source=filtered_per_source,
            cache_hits=cache_hits,
        )

    async def _fetch_source(self, source: str, query: str, max_results: int) -> dict[str, object]:
        cached = self.repository.get_query_cache(query, source, freshness_hours=self.settings.query_cache_hours)
        cache_hit = cached is not None
        raw_papers = cached if cached is not None else await self.clients[source].search(query, self._source_limit(source, max_results))

        if not cache_hit:
            if source == "semantic_scholar":
                raw_papers = await self.clients[source].enrich_citations(raw_papers)
            self.repository.save_query_cache(query, source, raw_papers)

        filtered = self._apply_quality_filters(raw_papers)
        filtered_count = max(0, len(raw_papers) - len(filtered))
        logger.info(
            "ingestion_source_complete",
            extra={
                "source": source,
                "raw_count": len(raw_papers),
                "filtered_count": filtered_count,
                "cache_hit": cache_hit,
            },
        )
        return {
            "papers": filtered,
            "filtered_count": filtered_count,
            "cache_hit": cache_hit,
        }

    @staticmethod
    def _source_limit(source: str, max_results: int) -> int:
        return min(SOURCE_CAPS.get(source, max_results), max_results if max_results > 0 else SOURCE_CAPS.get(source, 40))

    @staticmethod
    def _apply_quality_filters(papers: list[Paper]) -> list[Paper]:
        filtered: list[Paper] = []
        for paper in papers:
            title = (paper.title or "").lower()
            if "retracted" in title or "erratum" in title:
                continue
            if paper.year is not None and paper.year < 1990:
                continue
            if not paper.abstract or not paper.abstract.strip():
                continue
            if word_count(paper.abstract) < 80:
                continue
            filtered.append(paper)
        return filtered

    def _dedupe(self, papers: list[Paper]) -> tuple[list[Paper], int]:
        kept: list[Paper] = []
        dedup_removed = 0
        for paper in papers:
            duplicate_index = self._find_duplicate_index(kept, paper)
            if duplicate_index is None:
                kept.append(paper)
                continue
            dedup_removed += 1
            kept[duplicate_index] = self._prefer_more_populated(kept[duplicate_index], paper)
        return kept, dedup_removed

    def _find_duplicate_index(self, papers: list[Paper], candidate: Paper) -> int | None:
        normalized_candidate = normalize_title_for_dedupe(candidate.title)
        for index, paper in enumerate(papers):
            if paper.doi and candidate.doi and paper.doi.lower() == candidate.doi.lower():
                return index

            if paper.doi or candidate.doi:
                continue

            normalized_existing = normalize_title_for_dedupe(paper.title)
            if normalized_existing == normalized_candidate:
                return index
            if self._title_distance(normalized_existing, normalized_candidate) <= 3:
                return index
        return None

    @staticmethod
    def _title_distance(left: str, right: str) -> int:
        if Levenshtein is not None:
            return int(Levenshtein.distance(left, right))
        if left == right:
            return 0
        if abs(len(left) - len(right)) > 3:
            return 99
        previous = list(range(len(right) + 1))
        for row, left_char in enumerate(left, start=1):
            current = [row]
            for col, right_char in enumerate(right, start=1):
                cost = 0 if left_char == right_char else 1
                current.append(min(current[-1] + 1, previous[col] + 1, previous[col - 1] + cost))
            previous = current
        return previous[-1]

    @staticmethod
    def _prefer_more_populated(left: Paper, right: Paper) -> Paper:
        return right if IngestionService._population_score(right) > IngestionService._population_score(left) else left

    @staticmethod
    def _population_score(paper: Paper) -> int:
        abstract_tokens = len(tokenize_text(paper.abstract or "", drop_stop_words=True))
        keyword_tokens = len(paper.keywords) + len(paper.mesh_terms)
        return sum(
            [
                10 if paper.doi else 0,
                5 if paper.citation_count is not None else 0,
                3 if paper.url else 0,
                2 if paper.year else 0,
                abstract_tokens,
                keyword_tokens,
                len(paper.authors),
            ]
        )
