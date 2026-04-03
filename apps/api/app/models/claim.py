from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClaimDirection(str, Enum):
    positive = "positive"
    negative = "negative"
    null = "null"


class ClaimMagnitude(str, Enum):
    strong = "strong"
    moderate = "moderate"
    weak = "weak"
    null = "null"


class PaperClaim(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_id: str
    provider: str = "mock"
    model: str | None = None
    found: bool = False
    claim: str | None = None
    direction: ClaimDirection = ClaimDirection.null
    magnitude: ClaimMagnitude = ClaimMagnitude.null
    population: str | None = None
    outcome: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    skip_reason: str | None = None
    discarded: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InputClaim(BaseModel):
    claim: str
    direction: ClaimDirection = ClaimDirection.null
    search_query: str
    population: str | None = None
    outcome: str | None = None
