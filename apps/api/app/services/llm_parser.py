from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class ClaimResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    found: bool
    claim: str | None = None
    direction: Literal["positive", "negative", "null"] = "null"
    magnitude: Literal["strong", "moderate", "weak", "null"] = "null"
    population: str | None = None
    outcome: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ContradictionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_contradiction: bool
    score: float = Field(ge=0.0, le=1.0)
    type: Literal["direct", "conditional", "methodological", "null"]
    explanation: str
    could_both_be_true: bool = True
    key_difference: str | None = None


class InputClaimResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str
    direction: Literal["positive", "negative", "null"] = "null"
    search_query: str
    population: str | None = None
    outcome: str | None = None


class InputClaimsResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claims: list[InputClaimResult] = Field(default_factory=list)


def parse_llm_json(raw: str, model_class: type[BaseModel]) -> BaseModel | None:
    if raw is None:
        logger.debug("llm_parse_failed", extra={"raw_response": None, "reason": "empty"})
        return None

    candidates = []
    stripped = raw.strip()
    candidates.append(stripped)

    fenced = re.sub(r"^```json\s*|\s*```$", "", stripped, flags=re.IGNORECASE | re.DOTALL).strip()
    if fenced and fenced not in candidates:
        candidates.append(fenced)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        extracted = stripped[start : end + 1].strip()
        if extracted not in candidates:
            candidates.append(extracted)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            return model_class.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            continue

    logger.debug("llm_parse_failed", extra={"raw_response": raw})
    return None
