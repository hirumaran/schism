from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .paper import Paper


def canonicalize_pair(paper_a_id: str, paper_b_id: str) -> tuple[str, str]:
    return tuple(sorted([paper_a_id, paper_b_id]))


def build_pair_key(paper_a_id: str, paper_b_id: str) -> str:
    left, right = canonicalize_pair(paper_a_id, paper_b_id)
    digest = hashlib.sha1(f"{left}|{right}".encode("utf-8")).hexdigest()
    return f"pair_{digest[:20]}"


class ContradictionType(str, Enum):
    direct = "direct"
    conditional = "conditional"
    methodological = "methodological"
    null = "null"


class ContradictionMode(str, Enum):
    paper_vs_corpus = "paper_vs_corpus"
    corpus_vs_corpus = "corpus_vs_corpus"


class ContradictionPair(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_a_id: str
    paper_b_id: str
    mode: ContradictionMode = ContradictionMode.corpus_vs_corpus
    provider: str = "mock"
    model: str | None = None
    cluster_id: str | None = None
    pair_key: str | None = None
    raw_score: float = Field(default=0.0, ge=0.0, le=1.0)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    type: ContradictionType | None = None
    explanation: str = ""
    is_contradiction: bool = False
    could_both_be_true: bool = True
    key_difference: str | None = None
    paper_a_claim: str | None = None
    paper_b_claim: str | None = None
    paper_a: Paper | None = None
    paper_b: Paper | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


    def model_post_init(self, __context: Any) -> None:
        if self.pair_key is None:
            self.pair_key = build_pair_key(self.paper_a_id, self.paper_b_id)

    @computed_field
    @property
    def claim_a_text(self) -> str | None:
        return self.paper_a_claim

    @computed_field
    @property
    def claim_b_text(self) -> str | None:
        return self.paper_b_claim

    @computed_field
    @property
    def paper_a_title(self) -> str:
        return self.paper_a.title if self.paper_a else ""

    @computed_field
    @property
    def paper_b_title(self) -> str:
        return self.paper_b.title if self.paper_b else ""

    @computed_field
    @property
    def contradiction_score(self) -> float:
        return self.score

    @computed_field
    @property
    def contradiction_type(self) -> str:
        return self.type.value if self.type else ""

