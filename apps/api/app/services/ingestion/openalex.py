from __future__ import annotations

import httpx

from app.models.paper import Paper
from app.services.ingestion.base import BaseIngester, RateLimiter


def _reconstruct_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    max_position = max((position for positions in index.values() for position in positions), default=-1)
    if max_position < 0:
        return None
    tokens = [""] * (max_position + 1)
    for token, positions in index.items():
        for position in positions:
            if 0 <= position < len(tokens):
                tokens[position] = token
    text = " ".join(token for token in tokens if token)
    return text or None


class OpenAlexClient(BaseIngester):
    source = "openalex"
    rate_limiter = RateLimiter(concurrency=3, delay_seconds=0.1)

    def __init__(self, user_agent: str, contact_email: str | None) -> None:
        self.user_agent = user_agent
        self.contact_email = contact_email

    async def search(self, query: str, max_results: int) -> list[Paper]:
        params = {
            "search": query,
            "per-page": max_results,
            "filter": "type:journal-article",
        }
        if self.contact_email:
            params["mailto"] = self.contact_email

        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": self.user_agent},
        ) as client:
            response = await self.fetch_with_retry(client, "https://api.openalex.org/works", params=params)
            response.raise_for_status()

        payload = response.json()
        papers: list[Paper] = []
        for item in payload.get("results", []):
            identifier = item.get("id")
            title = item.get("title")
            if not identifier or not title:
                continue
            doi = item.get("doi")
            if isinstance(doi, str):
                doi = doi.removeprefix("https://doi.org/")
            keywords = [
                keyword.get("display_name", "")
                for keyword in item.get("keywords", [])
                if keyword.get("display_name")
            ]
            papers.append(
                Paper(
                    source=self.source,
                    external_id=identifier.rsplit("/", 1)[-1],
                    doi=doi,
                    title=title,
                    abstract=_reconstruct_abstract(item.get("abstract_inverted_index")),
                    year=item.get("publication_year"),
                    authors=[
                        authorship.get("author", {}).get("display_name", "")
                        for authorship in item.get("authorships", [])
                        if authorship.get("author", {}).get("display_name")
                    ],
                    citation_count=item.get("cited_by_count"),
                    url=item.get("primary_location", {}).get("landing_page_url"),
                    keywords=keywords,
                    raw=item,
                )
            )
        return papers
