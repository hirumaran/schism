from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from app.models.paper import Paper
from app.services.ingestion.base import BaseIngester, RateLimiter

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivClient(BaseIngester):
    source = "arxiv"
    rate_limiter = RateLimiter(concurrency=1, delay_seconds=0.4)

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    async def search(self, query: str, max_results: int) -> list[Paper]:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": self.user_agent},
        ) as client:
            response = await self.fetch_with_retry(
                client,
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": f'all:"{query}"',
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            )
            response.raise_for_status()

        root = ET.fromstring(response.text)
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            identifier = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").rsplit("/", 1)[-1]
            if not identifier:
                continue

            links = entry.findall("atom:link", ATOM_NS)
            url = next((link.attrib.get("href") for link in links if link.attrib.get("rel") == "alternate"), None)
            papers.append(
                Paper(
                    source=self.source,
                    external_id=identifier,
                    doi=entry.findtext("arxiv:doi", default=None, namespaces=ATOM_NS),
                    title=self._clean(entry.findtext("atom:title", default="", namespaces=ATOM_NS)),
                    abstract=self._clean(entry.findtext("atom:summary", default="", namespaces=ATOM_NS)),
                    authors=[
                        self._clean(author.findtext("atom:name", default="", namespaces=ATOM_NS))
                        for author in entry.findall("atom:author", ATOM_NS)
                    ],
                    year=self._extract_year(entry.findtext("atom:published", default="", namespaces=ATOM_NS)),
                    url=url,
                    raw={"source": "arxiv"},
                )
            )
        return papers

    @staticmethod
    def _clean(value: str | None) -> str:
        return " ".join((value or "").split())

    @staticmethod
    def _extract_year(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value[:4])
        except ValueError:
            return None
