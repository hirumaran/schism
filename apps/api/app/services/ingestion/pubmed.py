from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from app.models.paper import Paper


class PubMedClient:
    source = "pubmed"

    def __init__(self, user_agent: str, contact_email: str | None) -> None:
        self.user_agent = user_agent
        self.contact_email = contact_email

    async def search(self, query: str, max_results: int) -> list[Paper]:
        params = {
            "db": "pubmed",
            "retmode": "json",
            "retmax": max_results,
            "term": query,
        }
        if self.contact_email:
            params["email"] = self.contact_email

        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": self.user_agent},
        ) as client:
            search_response = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params,
            )
            search_response.raise_for_status()
            search_payload = search_response.json()
            identifiers = search_payload.get("esearchresult", {}).get("idlist", [])
            if not identifiers:
                return []

            fetch_response = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                params={
                    "db": "pubmed",
                    "retmode": "xml",
                    "id": ",".join(identifiers),
                },
            )
            fetch_response.raise_for_status()

        return self._parse_articles(fetch_response.text)

    def _parse_articles(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        papers: list[Paper] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = article.findtext(".//PMID")
            title = self._clean(article.findtext(".//ArticleTitle"))
            if not pmid or not title:
                continue

            abstract_parts = [
                self._clean(text.text or "")
                for text in article.findall(".//Abstract/AbstractText")
                if self._clean(text.text or "")
            ]
            mesh_terms = [
                self._clean(descriptor.text or "")
                for descriptor in article.findall(".//MeshHeading/DescriptorName")
                if self._clean(descriptor.text or "")
            ]
            keywords = [
                self._clean(keyword.text or "")
                for keyword in article.findall(".//KeywordList/Keyword")
                if self._clean(keyword.text or "")
            ]
            authors = []
            for author in article.findall(".//AuthorList/Author"):
                last_name = self._clean(author.findtext("LastName"))
                fore_name = self._clean(author.findtext("ForeName"))
                collective = self._clean(author.findtext("CollectiveName"))
                if collective:
                    authors.append(collective)
                elif last_name or fore_name:
                    authors.append(" ".join(part for part in [fore_name, last_name] if part))

            doi = None
            for article_id in article.findall(".//ArticleIdList/ArticleId"):
                if article_id.attrib.get("IdType") == "doi" and article_id.text:
                    doi = article_id.text.strip()
                    break

            year = self._extract_year(article)
            papers.append(
                Paper(
                    source=self.source,
                    external_id=pmid,
                    doi=doi,
                    title=title,
                    abstract=" ".join(abstract_parts) or None,
                    year=year,
                    authors=authors,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    keywords=keywords,
                    mesh_terms=mesh_terms,
                    raw={"pmid": pmid},
                )
            )
        return papers

    @staticmethod
    def _clean(value: str | None) -> str:
        return " ".join((value or "").split())

    @classmethod
    def _extract_year(cls, article: ET.Element) -> int | None:
        candidates = [
            article.findtext(".//PubDate/Year"),
            article.findtext(".//ArticleDate/Year"),
            article.findtext(".//DateCompleted/Year"),
        ]
        for candidate in candidates:
            if candidate and candidate.isdigit():
                return int(candidate)
        return None

