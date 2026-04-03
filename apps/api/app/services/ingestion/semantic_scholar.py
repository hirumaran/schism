from __future__ import annotations

import asyncio

import httpx

from app.models.paper import Paper
from app.services.ingestion.base import BaseIngester, RateLimiter


class SemanticScholarClient(BaseIngester):
    source = "semantic_scholar"
    rate_limiter = RateLimiter(concurrency=5, delay_seconds=0.05)

    async def search(self, query: str, max_results: int) -> list[Paper]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await self.fetch_with_retry(
                client,
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": max_results,
                    "fields": ",".join(
                        [
                            "paperId",
                            "title",
                            "abstract",
                            "year",
                            "authors",
                            "citationCount",
                            "url",
                            "externalIds",
                            "fieldsOfStudy",
                        ]
                    ),
                },
            )
            response.raise_for_status()

        payload = response.json()
        papers: list[Paper] = []
        for item in payload.get("data", []):
            paper_id = item.get("paperId")
            title = item.get("title")
            if not paper_id or not title:
                continue
            external_ids = item.get("externalIds") or {}
            papers.append(
                Paper(
                    source=self.source,
                    external_id=paper_id,
                    doi=external_ids.get("DOI"),
                    title=title,
                    abstract=item.get("abstract"),
                    year=item.get("year"),
                    authors=[author.get("name", "") for author in item.get("authors", []) if author.get("name")],
                    citation_count=item.get("citationCount"),
                    url=item.get("url"),
                    keywords=[value for value in item.get("fieldsOfStudy", []) if isinstance(value, str)],
                    raw=item,
                )
            )
        return papers

    async def enrich_citations(self, papers: list[Paper]) -> list[Paper]:
        semaphore = asyncio.Semaphore(5)

        async def enrich(paper: Paper) -> None:
            async with semaphore:
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await self.fetch_with_retry(
                            client,
                            f"https://api.semanticscholar.org/graph/v1/paper/{paper.external_id}",
                            params={"fields": "citationCount,influentialCitationCount"},
                        )
                        response.raise_for_status()
                        payload = response.json()
                except Exception:
                    return

                citation_count = payload.get("citationCount")
                influential = payload.get("influentialCitationCount")
                if isinstance(citation_count, int):
                    paper.citation_count = citation_count
                if isinstance(influential, int):
                    paper.influential_citation_count = influential

        await asyncio.gather(*(enrich(paper) for paper in papers))
        return papers
