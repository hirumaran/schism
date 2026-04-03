from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from app.models.paper import Paper
from app.services.ingestion.arxiv import ArxivClient
from app.services.ingestion.openalex import OpenAlexClient
from app.services.ingestion.pubmed import PubMedClient
from app.services.ingestion.semantic_scholar import SemanticScholarClient


@dataclass(slots=True)
class IngestionResult:
    papers: list[Paper]
    warnings: list[str]


class IngestionService:
    def __init__(self, user_agent: str, contact_email: str | None) -> None:
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

        per_source_limit = max(1, math.ceil(max_results / len(selected_sources)))
        tasks = {
            source: asyncio.create_task(self.clients[source].search(query, per_source_limit))
            for source in selected_sources
        }
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

        warnings: list[str] = []
        papers: list[Paper] = []
        for source, response in zip(tasks.keys(), responses, strict=False):
            if isinstance(response, Exception):
                warnings.append(f"{source} search failed: {response}")
                continue
            papers.extend(response)

        deduped = self._dedupe(papers)
        ranked = sorted(
            deduped,
            key=lambda paper: ((paper.citation_count or 0), (paper.year or 0), len(paper.abstract or "")),
            reverse=True,
        )
        return IngestionResult(papers=ranked[:max_results], warnings=warnings)

    @staticmethod
    def _dedupe(papers: list[Paper]) -> list[Paper]:
        deduped: dict[str, Paper] = {}
        for paper in papers:
            key = paper.dedupe_key()
            current = deduped.get(key)
            if current is None:
                deduped[key] = paper
                continue
            if (paper.citation_count or 0) > (current.citation_count or 0):
                deduped[key] = paper
        return list(deduped.values())

