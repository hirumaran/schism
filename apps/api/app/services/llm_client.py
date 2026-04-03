from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.models.claim import ClaimDirection, PaperClaim
from app.models.contradiction import ContradictionPair, ContradictionType
from app.models.paper import Paper, normalize_text

CLAIM_PROMPT = """
Extract the primary conclusion of this paper as a single declarative sentence.
Focus on the main empirical finding, not the method.
Return JSON with keys:
- claim: string
- direction: positive | negative | null
- confidence: 0.0 to 1.0
- quality: 0.0 to 1.0
- rationale: short string

Paper title: {title}
Paper abstract: {abstract}
"""

CONTRADICTION_PROMPT = """
Paper A claim: {claim_a}
Paper B claim: {claim_b}

Rate the contradiction between these two claims.
Return JSON with keys:
- score: 0.0 to 1.0
- type: direct | conditional | methodological | null
- explanation: short string
- is_contradiction: boolean
"""


@dataclass(slots=True)
class ProviderContext:
    provider: str = "mock"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None

    @property
    def normalized_provider(self) -> str:
        return (self.provider or "mock").strip().lower()


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def extract_claim(self, paper: Paper, context: ProviderContext) -> PaperClaim:
        fallback = self._heuristic_claim(paper, context)
        if self._should_use_fallback(context):
            return fallback

        prompt = CLAIM_PROMPT.format(
            title=paper.title.strip(),
            abstract=(paper.abstract or "").strip() or "No abstract available.",
        )

        try:
            payload = await self._invoke_json(prompt, context)
        except Exception:
            return fallback

        return PaperClaim(
            paper_id=paper.id,
            provider=context.normalized_provider,
            model=context.model,
            claim=str(payload.get("claim") or fallback.claim).strip(),
            direction=self._coerce_direction(payload.get("direction")) or fallback.direction,
            confidence=self._bounded_float(payload.get("confidence"), fallback.confidence),
            quality=self._bounded_float(payload.get("quality"), fallback.quality),
            rationale=str(payload.get("rationale") or fallback.rationale or "").strip() or None,
            raw=payload,
        )

    async def score_contradiction(
        self,
        claim_a: PaperClaim,
        claim_b: PaperClaim,
        paper_a: Paper,
        paper_b: Paper,
        context: ProviderContext,
    ) -> ContradictionPair:
        fallback = self._heuristic_contradiction(claim_a, claim_b, paper_a, paper_b, context)
        if self._should_use_fallback(context):
            return fallback

        prompt = CONTRADICTION_PROMPT.format(claim_a=claim_a.claim, claim_b=claim_b.claim)
        try:
            payload = await self._invoke_json(prompt, context)
        except Exception:
            return fallback

        return ContradictionPair(
            paper_a_id=paper_a.id,
            paper_b_id=paper_b.id,
            provider=context.normalized_provider,
            model=context.model,
            score=self._bounded_float(payload.get("score"), fallback.score),
            type=self._coerce_type(payload.get("type")) or fallback.type,
            explanation=str(payload.get("explanation") or fallback.explanation).strip(),
            is_contradiction=self._coerce_bool(payload.get("is_contradiction"), fallback.is_contradiction),
            raw=payload,
        )

    async def _invoke_json(self, prompt: str, context: ProviderContext) -> dict[str, Any]:
        provider = context.normalized_provider
        timeout = httpx.Timeout(self.settings.llm_timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "openai":
                response = await client.post(
                    self._provider_url(provider, context.base_url),
                    headers={
                        "Authorization": f"Bearer {context.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": context.model or "gpt-4.1-mini",
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a careful research assistant. Return valid JSON only.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                return self._extract_json(content)

            if provider == "anthropic":
                response = await client.post(
                    self._provider_url(provider, context.base_url),
                    headers={
                        "x-api-key": context.api_key or "",
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": context.model or "claude-3-5-sonnet-latest",
                        "max_tokens": 512,
                        "temperature": 0.1,
                        "system": "You are a careful research assistant. Return valid JSON only.",
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                content = "".join(
                    block.get("text", "")
                    for block in payload.get("content", [])
                    if block.get("type") == "text"
                )
                return self._extract_json(content)

            if provider == "ollama":
                headers = {"Content-Type": "application/json"}
                if context.api_key:
                    headers["Authorization"] = f"Bearer {context.api_key}"
                response = await client.post(
                    self._provider_url(provider, context.base_url),
                    headers=headers,
                    json={
                        "model": context.model or "llama3.1",
                        "stream": False,
                        "format": "json",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a careful research assistant. Return valid JSON only.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["message"]["content"]
                return self._extract_json(content)

        raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def _should_use_fallback(context: ProviderContext) -> bool:
        if context.normalized_provider in {"mock", "local", "heuristic"}:
            return True
        if context.normalized_provider == "ollama":
            return False
        return not bool(context.api_key)

    def _provider_url(self, provider: str, base_url: str | None) -> str:
        if provider == "openai":
            root = (base_url or "https://api.openai.com").rstrip("/")
            return root if root.endswith("/v1/chat/completions") else f"{root}/v1/chat/completions"
        if provider == "anthropic":
            root = (base_url or "https://api.anthropic.com").rstrip("/")
            return root if root.endswith("/v1/messages") else f"{root}/v1/messages"
        if provider == "ollama":
            root = (base_url or "http://localhost:11434").rstrip("/")
            return root if root.endswith("/api/chat") else f"{root}/api/chat"
        raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def _extract_json(content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            content = "".join(str(item) for item in content)
        if not isinstance(content, str):
            raise ValueError("LLM response was not text.")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    @staticmethod
    def _coerce_direction(value: Any) -> ClaimDirection | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"positive", "negative", "null"}:
            return ClaimDirection(normalized)
        return None

    @staticmethod
    def _coerce_type(value: Any) -> ContradictionType | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"direct", "conditional", "methodological", "null"}:
            return ContradictionType(normalized)
        return None

    @staticmethod
    def _bounded_float(value: Any, default: float) -> float:
        try:
            candidate = float(value)
        except (TypeError, ValueError):
            candidate = default
        return max(0.0, min(1.0, candidate))

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return default

    def _heuristic_claim(self, paper: Paper, context: ProviderContext) -> PaperClaim:
        abstract = re.sub(r"\s+", " ", (paper.abstract or "").strip())
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", abstract) if segment.strip()]
        prioritized = [
            sentence
            for sentence in sentences
            if any(
                cue in sentence.lower()
                for cue in [
                    "we found",
                    "results show",
                    "conclusion",
                    "demonstrat",
                    "significant",
                    "associated",
                    "improve",
                    "reduc",
                    "did not",
                ]
            )
        ]
        chosen = prioritized[0] if prioritized else (sentences[-1] if sentences else paper.title)
        direction = self._detect_direction(chosen)
        abstract_word_count = len(abstract.split())
        quality = 0.25
        if abstract_word_count >= 40:
            quality = 0.65
        if abstract_word_count >= 120:
            quality = 0.85
        confidence = 0.55 if chosen != paper.title else 0.35
        return PaperClaim(
            paper_id=paper.id,
            provider=context.normalized_provider,
            model=context.model,
            claim=chosen,
            direction=direction,
            confidence=confidence,
            quality=quality,
            rationale="Heuristic extraction from the abstract.",
            raw={"mode": "heuristic"},
        )

    def _heuristic_contradiction(
        self,
        claim_a: PaperClaim,
        claim_b: PaperClaim,
        paper_a: Paper,
        paper_b: Paper,
        context: ProviderContext,
    ) -> ContradictionPair:
        tokens_a = {token for token in normalize_text(claim_a.claim).split() if len(token) > 2}
        tokens_b = {token for token in normalize_text(claim_b.claim).split() if len(token) > 2}
        overlap = len(tokens_a & tokens_b)
        denominator = max(1, len(tokens_a | tokens_b))
        jaccard = overlap / denominator

        direction_conflict = (
            claim_a.direction is not None
            and claim_b.direction is not None
            and claim_a.direction != claim_b.direction
            and ClaimDirection.null not in {claim_a.direction, claim_b.direction}
        )
        one_null = ClaimDirection.null in {claim_a.direction, claim_b.direction}
        type_value: ContradictionType | None = None
        score = 0.15
        explanation = "Claims appear broadly consistent."
        is_contradiction = False

        if direction_conflict and jaccard >= 0.15:
            score = min(1.0, 0.65 + (jaccard * 0.3))
            type_value = ContradictionType.direct
            explanation = "Claims use overlapping topic language but point in opposite directions."
            is_contradiction = True
        elif one_null and jaccard >= 0.2:
            score = 0.55
            type_value = ContradictionType.conditional
            explanation = "One claim is directional while the other is null or inconclusive."
        elif jaccard < 0.12:
            score = 0.1
            explanation = "Claims do not share enough lexical overlap to count as a contradiction."
        else:
            score = 0.32
            type_value = ContradictionType.methodological
            explanation = "Claims are related but do not clearly reverse each other."

        return ContradictionPair(
            paper_a_id=paper_a.id,
            paper_b_id=paper_b.id,
            provider=context.normalized_provider,
            model=context.model,
            score=score,
            type=type_value,
            explanation=explanation,
            is_contradiction=is_contradiction,
            raw={"mode": "heuristic", "jaccard": round(jaccard, 4)},
        )

    @staticmethod
    def _detect_direction(text: str) -> ClaimDirection:
        lowered = text.lower()
        negative_markers = [
            "no significant",
            "did not",
            "not associated",
            "without effect",
            "failed to",
            "ineffective",
        ]
        positive_markers = [
            "improv",
            "increase",
            "decrease",
            "reduc",
            "associated",
            "benefit",
            "effective",
            "significant",
        ]

        if any(marker in lowered for marker in negative_markers):
            return ClaimDirection.negative
        if any(marker in lowered for marker in positive_markers):
            return ClaimDirection.positive
        return ClaimDirection.null
