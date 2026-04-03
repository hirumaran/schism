from __future__ import annotations

import httpx

from app.models.paper import Paper


class SemanticScholarClient:
    source = "semantic_scholar"

    async def search(self, query: str, max_results: int) -> list[Paper]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
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

