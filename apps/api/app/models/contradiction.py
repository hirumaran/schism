from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def build_pair_key(claim_a: str, claim_b: str, paper_a_id: str, paper_b_id: str) -> str:
    normalized = sorted(
        [
            f"{paper_a_id}:{claim_a.strip().lower()}",
            f"{paper_b_id}:{claim_b.strip().lower()}",
        ]
    )
    digest = hashlib.sha1("|".join(normalized).encode("utf-8")).hexdigest()
    return f"pair_{digest[:20]}"


class ContradictionType(str, Enum):
    direct = "direct"
    conditional = "conditional"
    methodological = "methodological"
    null = "null"


class ContradictionPair(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_a_id: str
    paper_b_id: str
    provider: str = "mock"
    model: str | None = None
    cluster_id: str | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    type: ContradictionType | None = None
    explanation: str = ""
    is_contradiction: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

