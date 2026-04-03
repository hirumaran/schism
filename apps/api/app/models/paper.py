from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def tokenize_text(value: str, *, drop_stop_words: bool = False, min_length: int = 2) -> set[str]:
    tokens = {
        token
        for token in normalize_text(value).split()
        if len(token) >= min_length and (not drop_stop_words or token not in STOP_WORDS)
    }
    return tokens


def word_count(value: str | None) -> int:
    return len(re.findall(r"\b\w+\b", value or ""))


def jaccard_similarity(left: str | None, right: str | None, *, drop_stop_words: bool = False) -> float:
    left_tokens = tokenize_text(left or "", drop_stop_words=drop_stop_words)
    right_tokens = tokenize_text(right or "", drop_stop_words=drop_stop_words)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def normalize_title_for_dedupe(title: str) -> str:
    normalized = normalize_text(title)
    for prefix in ("the ", "a ", "an "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized.strip()


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip().lower())


def build_query_cache_key(query: str, source: str) -> str:
    digest = hashlib.sha256(f"{normalize_query(query)}::{source}".encode("utf-8")).hexdigest()
    return digest


def build_paper_id(source: str, external_id: str, doi: str | None, title: str) -> str:
    fingerprint = doi or f"{source}:{external_id}" or title
    digest = hashlib.sha1(normalize_text(fingerprint).encode("utf-8")).hexdigest()
    return f"paper_{digest[:16]}"


class Paper(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    source: str
    external_id: str
    doi: str | None = None
    title: str
    abstract: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    citation_count: int | None = None
    influential_citation_count: int | None = None
    url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    mesh_terms: list[str] = Field(default_factory=list)
    magnitude: str | None = None
    population: str | None = None
    outcome: str | None = None
    embedding_id: str | None = None
    relevance_score: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = build_paper_id(self.source, self.external_id, self.doi, self.title)
        if self.embedding_id is None:
            self.embedding_id = f"embed_{self.id}"

    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{normalize_text(self.doi)}"
        year_fragment = str(self.year or "")
        return f"title:{normalize_title_for_dedupe(self.title)}:{year_fragment}"

    def topic_tokens(self) -> set[str]:
        values = [
            self.title,
            self.abstract or "",
            *(self.keywords or []),
            *(self.mesh_terms or []),
            self.population or "",
            self.outcome or "",
        ]
        tokens: set[str] = set()
        for value in values:
            tokens.update(tokenize_text(value, drop_stop_words=True, min_length=3))
        return tokens
