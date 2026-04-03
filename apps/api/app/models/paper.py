from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


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
    url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    mesh_terms: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = build_paper_id(self.source, self.external_id, self.doi, self.title)

    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{normalize_text(self.doi)}"
        year_fragment = str(self.year or "")
        return f"title:{normalize_text(self.title)}:{year_fragment}"

    def topic_tokens(self) -> set[str]:
        values = [self.title, *(self.keywords or []), *(self.mesh_terms or [])]
        tokens: set[str] = set()
        for value in values:
            tokens.update(token for token in normalize_text(value).split() if len(token) > 2)
        return tokens

