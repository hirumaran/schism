from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.models.claim import ClaimDirection, ClaimMagnitude, InputClaim, PaperClaim
from app.models.contradiction import (
    ContradictionMode,
    ContradictionPair,
    ContradictionType,
)
from app.models.report import PaperBreakdown, CoreConcept, SearchQueries
from app.models.paper import Paper, jaccard_similarity, tokenize_text, word_count
from app.services.llm_parser import (
    ClaimResult,
    ContradictionResult,
    InputClaimsResult,
    parse_llm_json,
)
from app.services.summarizer import DocumentCompressor

logger = logging.getLogger(__name__)

_REDACTED = "[REDACTED]"
_REDACTED_KEYS = frozenset({"api_key", "key", "token", "authorization"})


def _redact(value: str | None) -> str:
    if value is None:
        return _REDACTED
    if len(value) <= 4:
        return _REDACTED
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


CLAIM_SYSTEM_PROMPT = """
You are a scientific claim extractor. Your only job is to identify
the single most important empirical finding from a research paper
abstract. You must return valid JSON only - no markdown, no
explanation, no preamble.

Rules:
- The claim must be a specific, falsifiable statement of result
- The claim must include the direction of the effect
- Do not include methodology, sample size, or caveats in the claim
- Do not start with "This study", "The paper", "We found"
- Write in third person declarative form
- If no clear empirical finding exists, set found=false
""".strip()

CLAIM_USER_PROMPT = """
Title: {title}
Abstract: {abstract}

Return JSON:
{{
  "found": true,
  "claim": "single declarative sentence with direction of effect",
  "direction": "positive|negative|null",
  "magnitude": "strong|moderate|weak|null",
  "population": "who or what was studied, 2-4 words",
  "outcome": "what was measured, 2-4 words",
  "confidence": 0.0
}}
""".strip()

CLAIM_FALLBACK_PROMPT = """
Return valid JSON only:
{{
  "found": true,
  "claim": "single finding sentence",
  "direction": "positive|negative|null",
  "confidence": 0.0
}}

Title: {title}
Abstract: {abstract}
""".strip()

INPUT_CLAIMS_SYSTEM_PROMPT = """
You are extracting research claims from a paper that a user has
provided. Extract ALL distinct empirical claims or findings, not
just one. Each claim should be independently searchable.
Return valid JSON only.
""".strip()

INPUT_CLAIMS_USER_PROMPT = """
{best_section}

Extract up to 5 distinct empirical claims from this text.
For each claim identify what could be searched to find
contradicting evidence.

Return JSON:
{{
  "claims": [
    {{
      "claim": "declarative sentence",
      "direction": "positive|negative|null",
      "search_query": "3-6 word query to find contradicting papers",
      "population": "who/what was studied",
      "outcome": "what was measured"
    }}
  ]
}}
""".strip()

CONTRADICTION_SYSTEM_PROMPT = """
You are a scientific contradiction analyst. You compare pairs of
research findings and determine whether they genuinely contradict
each other. Return valid JSON only - no markdown, no explanation.

Contradiction types:
- "direct": same population, same outcome, opposite direction
- "conditional": same outcome, opposite direction, but different
  conditions, doses, or subgroups
- "methodological": same question, different methodology leads to
  different conclusions
- "null": findings are compatible when full context is considered
""".strip()

CONTRADICTION_USER_PROMPT = """
Finding A (from {year_a}): "{claim_a}"
Population A: {population_a}
Outcome A: {outcome_a}

Finding B (from {year_b}): "{claim_b}"
Population B: {population_b}
Outcome B: {outcome_b}

Questions:
1. Do these findings genuinely contradict each other?
2. Could both be true simultaneously under different conditions?
3. Is this a direct contradiction or a methodological difference?

Return JSON:
{{
  "is_contradiction": false,
  "score": 0.0,
  "type": "direct|conditional|methodological|null",
  "explanation": "2-3 sentences explaining why these do or do not contradict",
  "could_both_be_true": true,
  "key_difference": "the most likely reason for the discrepancy in 8 words or fewer"
}}
""".strip()


BREAKDOWN_SYSTEM_PROMPT = """
You are a brilliant science communicator who explains complex research papers to smart but non-expert readers.
Your task is to break down a paper into clear, understandable components.
Rules:
- Start with the simplest possible explanation.
- Build up to technical depth.
- Never use undefined acronyms.
- Treat the reader as a smart non-expert.
Return valid JSON exactly matching the requested format.
""".strip()

BREAKDOWN_USER_PROMPT = """
Paper Title: {title}
Paper Abstract: {abstract}
Other Text: {full_text}

Generate a breakdown of this paper with:
- one_line_summary
- high_level_explanation (2-3 sentences, plain language, no jargon)
- core_concepts (3-5 concepts with name, plain_explanation, technical_explanation, why_it_matters)
- methodology_summary
- key_findings (3-5 bullet points)
- limitations (2-3 limitations the paper acknowledges or that are apparent)
- related_fields
- search_queries (with "youtube" x3 for explainers, "academic" x2-3 for related papers, "general" x2-3 for plain-language search)

Return ONLY JSON.
""".strip()


HEDGING_PATTERNS = [
    "this paper investigates",
    "this study investigates",
    "we propose a method",
    "further research is needed",
    "future research is needed",
    "this article reviews",
    "this paper presents",
]


@dataclass(slots=True)
class ProviderContext:
    provider: str = "mock"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    embedding_provider: str | None = None
    embedding_api_key: str | None = None
    secondary_provider: str | None = None
    secondary_api_key: str | None = None
    secondary_model: str | None = None
    secondary_base_url: str | None = None
    failover_meta: FailoverMeta | None = None

    @property
    def normalized_provider(self) -> str:
        return (self.provider or "mock").strip().lower()


@dataclass(slots=True)
class FailoverMeta:
    failover_occurred: bool = False
    provider_used: str | None = None
    primary_error: str | None = None


_RETRIABLE_PATTERNS = [
    "rate limit",
    "quota",
    "insufficient credits",
    "overloaded",
    "capacity",
]


def _is_retriable(exc: Exception, status_code: int | None) -> bool:
    if status_code in (429, 402, 503):
        return True
    msg = str(exc).lower()
    return any(p in msg for p in _RETRIABLE_PATTERNS)


def _is_non_retriable_4xx(status_code: int | None) -> bool:
    return status_code in (400, 401)


class LLMClient:
    def __init__(
        self, settings: Settings, compressor: DocumentCompressor | None = None
    ) -> None:
        self.settings = settings
        self.compressor = compressor

    def _compress_abstract(
        self,
        abstract: str,
        compressor: DocumentCompressor | None,
    ) -> str:
        if compressor is None or not abstract:
            return abstract
        try:
            compressed = compressor.compress(abstract)
            # If the compressor returns None, or very short text, fall back to original
            if not compressed or len(compressed.split()) < 20:
                return abstract
            return compressed
        except Exception as exc:
            logger.warning("abstract_compression_failed", extra={"error": str(exc)})
            return abstract

    async def generate_paper_breakdown(
        self, paper: Paper, context: ProviderContext
    ) -> PaperBreakdown | None:
        if self._should_use_fallback(context):
            return None

        full_text = ""
        if hasattr(paper, "raw") and paper.raw and isinstance(paper.raw, dict):
            full_text = str(paper.raw.get("full_text", ""))[:4000]

        try:
            raw_content = await self.failover_invoke(
                system_prompt=BREAKDOWN_SYSTEM_PROMPT,
                user_prompt=BREAKDOWN_USER_PROMPT.format(
                    title=paper.title,
                    abstract=paper.abstract or "",
                    full_text=full_text,
                ),
                context=context,
            )
            result = parse_llm_json(raw_content, PaperBreakdown)
            if result:
                return PaperBreakdown.model_validate(result.model_dump())
        except Exception as exc:
            logger.warning("breakdown_generation_failed", extra={"error": str(exc)})
        return None

    async def extract_claim(self, paper: Paper, context: ProviderContext) -> PaperClaim:
        if word_count(paper.abstract) < 80:
            return PaperClaim(
                paper_id=paper.id,
                provider=context.normalized_provider,
                model=context.model,
                found=False,
                claim=None,
                confidence=0.0,
                quality=0.0,
                skip_reason="abstract_too_short",
                discarded=True,
                raw={"mode": "skipped"},
            )

        if self._should_use_fallback(context):
            return self._finalize_claim(self._heuristic_claim(paper, context))

        abstract = (paper.abstract or "").strip()
        compressed_abstract = self._compress_abstract(abstract, self.compressor)

        primary = await self._extract_claim_via_llm(
            paper=paper,
            context=context,
            user_prompt=CLAIM_USER_PROMPT.format(
                title=paper.title.strip(), abstract=compressed_abstract
            ),
        )
        if primary is not None:
            return self._finalize_claim(primary)

        fallback = await self._extract_claim_via_llm(
            paper=paper,
            context=context,
            user_prompt=CLAIM_FALLBACK_PROMPT.format(
                title=paper.title.strip(), abstract=compressed_abstract
            ),
        )
        if fallback is not None:
            return self._finalize_claim(fallback)

        return PaperClaim(
            paper_id=paper.id,
            provider=context.normalized_provider,
            model=context.model,
            found=False,
            claim=None,
            confidence=0.0,
            quality=0.0,
            skip_reason="extraction_failed",
            discarded=True,
            raw={"mode": "failed"},
        )

    async def extract_input_claims(
        self, best_section: str, context: ProviderContext
    ) -> list[InputClaim]:
        if self._should_use_fallback(context):
            return self._heuristic_input_claims(best_section)

        try:
            raw_content = await self.failover_invoke(
                system_prompt=INPUT_CLAIMS_SYSTEM_PROMPT,
                user_prompt=INPUT_CLAIMS_USER_PROMPT.format(
                    best_section=best_section.strip()
                ),
                context=context,
            )
        except Exception as exc:
            logger.warning(
                "input_claim_extraction_request_failed", extra={"error": str(exc)}
            )
            return self._heuristic_input_claims(best_section)

        result = parse_llm_json(raw_content, InputClaimsResult)
        if result is None:
            return self._heuristic_input_claims(best_section)

        parsed = InputClaimsResult.model_validate(result.model_dump())
        claims: list[InputClaim] = []
        seen_queries: set[str] = set()
        for item in parsed.claims[:5]:
            claim_text = re.sub(r"\s+", " ", item.claim.strip())
            search_query = re.sub(r"\s+", " ", item.search_query.strip())
            if not claim_text or not search_query:
                continue
            normalized_query = search_query.lower()
            if normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)
            claims.append(
                InputClaim(
                    claim=claim_text,
                    direction=ClaimDirection(item.direction),
                    search_query=search_query,
                    population=(item.population or "").strip() or None,
                    outcome=(item.outcome or "").strip() or None,
                )
            )
        return claims

    async def score_contradiction(
        self,
        claim_a: PaperClaim,
        claim_b: PaperClaim,
        paper_a: Paper,
        paper_b: Paper,
        context: ProviderContext,
    ) -> ContradictionPair:
        fallback = self._heuristic_contradiction(
            claim_a, claim_b, paper_a, paper_b, context
        )
        if self._should_use_fallback(context):
            return fallback

        raw_content = await self.failover_invoke(
            system_prompt=CONTRADICTION_SYSTEM_PROMPT,
            user_prompt=CONTRADICTION_USER_PROMPT.format(
                year_a=paper_a.year or "unknown",
                claim_a=claim_a.claim or "",
                population_a=claim_a.population or paper_a.population or "unknown",
                outcome_a=claim_a.outcome or paper_a.outcome or "unknown",
                year_b=paper_b.year or "unknown",
                claim_b=claim_b.claim or "",
                population_b=claim_b.population or paper_b.population or "unknown",
                outcome_b=claim_b.outcome or paper_b.outcome or "unknown",
            ),
            context=context,
        )
        result = parse_llm_json(raw_content, ContradictionResult)
        if result is None:
            return fallback

        parsed = ContradictionResult.model_validate(result.model_dump())
        return ContradictionPair(
            paper_a_id=paper_a.id,
            paper_b_id=paper_b.id,
            mode=ContradictionMode.corpus_vs_corpus,
            provider=context.normalized_provider,
            model=context.model,
            raw_score=parsed.score,
            score=parsed.score,
            type=ContradictionType(parsed.type),
            explanation=parsed.explanation.strip(),
            is_contradiction=parsed.is_contradiction,
            could_both_be_true=parsed.could_both_be_true,
            key_difference=(parsed.key_difference or "").strip() or None,
            paper_a_claim=claim_a.claim,
            paper_b_claim=claim_b.claim,
            paper_a=paper_a,
            paper_b=paper_b,
            raw={"mode": "llm"},
        )

    async def _extract_claim_via_llm(
        self, paper: Paper, context: ProviderContext, user_prompt: str
    ) -> PaperClaim | None:
        try:
            raw_content = await self.failover_invoke(
                system_prompt=CLAIM_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                context=context,
            )
        except Exception as exc:
            logger.warning("claim_extraction_request_failed", extra={"error": str(exc)})
            return None

        result = parse_llm_json(raw_content, ClaimResult)
        if result is None:
            return None

        parsed = ClaimResult.model_validate(result.model_dump())
        return PaperClaim(
            paper_id=paper.id,
            provider=context.normalized_provider,
            model=context.model,
            found=parsed.found,
            claim=(parsed.claim or "").strip() or None,
            direction=ClaimDirection(parsed.direction),
            magnitude=ClaimMagnitude(parsed.magnitude),
            population=(parsed.population or "").strip() or None,
            outcome=(parsed.outcome or "").strip() or None,
            confidence=parsed.confidence,
            quality=parsed.confidence,
            raw={"mode": "llm"},
        )

    async def _call_with_retry(self, call_fn, max_attempts: int = 3):
        for attempt in range(max_attempts):
            try:
                return await call_fn()
            except httpx.HTTPStatusError as exc:
                response = exc.response
                if response.status_code == 429:
                    wait = float(2**attempt)
                    logger.warning(
                        "llm_rate_limited",
                        extra={
                            "attempt": attempt,
                            "wait_seconds": wait,
                            "status_code": response.status_code,
                        },
                    )
                    await asyncio.sleep(wait)
                    continue
                if response.status_code >= 500 and attempt < max_attempts - 1:
                    await asyncio.sleep(1.0)
                    continue
                raise
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(1.0)
        raise RuntimeError(f"LLM call failed after {max_attempts} attempts")

    async def _invoke_text(
        self, system_prompt: str, user_prompt: str, context: ProviderContext
    ) -> str:
        provider = context.normalized_provider
        timeout = httpx.Timeout(self.settings.llm_timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "openai":

                async def call_openai():
                    response = await client.post(
                        self._provider_url(provider, context.base_url),
                        headers={
                            "Authorization": f"Bearer {context.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": context.model or "gpt-4.1-mini",
                            "temperature": 0.1,
                            "n": 1,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    response.raise_for_status()
                    return response

                response = await self._call_with_retry(call_openai)
                response.raise_for_status()
                payload = response.json()
                return payload["choices"][0]["message"]["content"]

            if provider == "anthropic":

                async def call_anthropic():
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
                            "system": system_prompt,
                            "messages": [{"role": "user", "content": user_prompt}],
                        },
                    )
                    response.raise_for_status()
                    return response

                response = await self._call_with_retry(call_anthropic)
                response.raise_for_status()
                payload = response.json()
                return "".join(
                    block.get("text", "")
                    for block in payload.get("content", [])
                    if block.get("type") == "text"
                )

            if provider == "ollama":
                headers = {"Content-Type": "application/json"}
                if context.api_key:
                    headers["Authorization"] = f"Bearer {context.api_key}"

                async def call_ollama():
                    response = await client.post(
                        self._provider_url(provider, context.base_url),
                        headers=headers,
                        json={
                            "model": context.model or "llama3.1",
                            "stream": False,
                            "format": "json",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    response.raise_for_status()
                    return response

                response = await self._call_with_retry(call_ollama)
                response.raise_for_status()
                payload = response.json()
                return payload["message"]["content"]

        raise ValueError(f"Unsupported provider: {provider}")

    async def failover_invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        context: ProviderContext,
    ) -> str:
        """Invoke LLM with automatic failover from primary to secondary provider on retriable errors.

        On success, sets context.failover_meta with failover_occurred=False.
        On failover success, sets context.failover_meta with failover_occurred=True.
        On both-providers-failed, raises a RuntimeError naming both providers.
        """
        primary_provider = context.normalized_provider
        secondary_provider = (context.secondary_provider or "").strip().lower() or None
        secondary_configured = (
            secondary_provider is not None
            and secondary_provider not in ("mock", "local", "")
            and (bool(context.secondary_api_key) or secondary_provider == "ollama")
        )

        # Try primary
        try:
            result = await self._invoke_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                context=context,
            )
            context.failover_meta = FailoverMeta(
                failover_occurred=False,
                provider_used=primary_provider,
                primary_error=None,
            )
            return result
        except Exception as primary_exc:
            primary_status: int | None = None
            if isinstance(primary_exc, httpx.HTTPStatusError):
                primary_status = primary_exc.response.status_code

            # Non-retriable: don't failover
            if _is_non_retriable_4xx(primary_status):
                raise

            # Not retriable: don't failover
            if not _is_retriable(primary_exc, primary_status):
                raise

            # No secondary configured: don't failover
            if not secondary_configured or not secondary_provider:
                raise

            # Build secondary context
            secondary_context = ProviderContext(
                provider=secondary_provider,
                api_key=context.secondary_api_key,
                model=context.secondary_model,
                base_url=context.secondary_base_url,
                embedding_provider=context.embedding_provider,
                embedding_api_key=context.embedding_api_key,
            )

            primary_error_summary = (
                f"HTTP {primary_status}"
                if primary_status
                else type(primary_exc).__name__
            )
            primary_error_detail = str(primary_exc)

            # Console log the failover (API key redacted)
            safe_key = _redact(context.api_key)
            logger.warning(
                "[Schism Failover] %s | Primary: %s | Error: %s (key: %s) | Retrying with: %s",
                primary_provider.upper(),
                primary_error_summary,
                type(primary_exc).__name__,
                safe_key,
                secondary_provider.upper(),
            )

            # Try secondary
            try:
                result = await self._invoke_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    context=secondary_context,
                )
                context.failover_meta = FailoverMeta(
                    failover_occurred=True,
                    provider_used=secondary_provider,
                    primary_error=(
                        f"{primary_error_summary}: {primary_error_detail[:100]}"
                    ),
                )
                return result
            except Exception as secondary_exc:
                secondary_status: int | None = None
                if isinstance(secondary_exc, httpx.HTTPStatusError):
                    secondary_status = secondary_exc.response.status_code
                secondary_error_summary = (
                    f"HTTP {secondary_status}"
                    if secondary_status
                    else type(secondary_exc).__name__
                )
                secondary_error_detail = str(secondary_exc)
                raise RuntimeError(
                    f"Both providers failed. Primary ({primary_provider}) error: "
                    f"{primary_error_summary}: {primary_error_detail}. "
                    f"Secondary ({secondary_provider}) error: "
                    f"{secondary_error_summary}: {secondary_error_detail}"
                ) from primary_exc

    def _provider_url(self, provider: str, base_url: str | None) -> str:
        if provider == "openai":
            root = (base_url or "https://api.openai.com").rstrip("/")
            return (
                root
                if root.endswith("/v1/chat/completions")
                else f"{root}/v1/chat/completions"
            )
        if provider == "anthropic":
            root = (base_url or "https://api.anthropic.com").rstrip("/")
            return root if root.endswith("/v1/messages") else f"{root}/v1/messages"
        if provider == "ollama":
            root = (base_url or "http://localhost:11434").rstrip("/")
            return root if root.endswith("/api/chat") else f"{root}/api/chat"
        raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def _should_use_fallback(context: ProviderContext) -> bool:
        if context.normalized_provider in {"mock", "local", "heuristic"}:
            return True
        if context.normalized_provider == "ollama":
            return False
        return not bool(context.api_key)

    def _finalize_claim(self, claim: PaperClaim) -> PaperClaim:
        if not claim.found or not claim.claim:
            claim.discarded = True
            claim.skip_reason = claim.skip_reason or "no_empirical_finding"
            claim.claim = None
            claim.quality = 0.0
            return claim

        normalized_claim = re.sub(r"\s+", " ", claim.claim.strip())
        claim.claim = normalized_claim
        reason = self._claim_validation_reason(normalized_claim, claim.confidence)
        if reason is not None:
            claim.found = False
            claim.discarded = True
            claim.skip_reason = reason
            claim.claim = None
            claim.quality = 0.0
            return claim

        claim.quality = max(claim.confidence, 0.5)
        return claim

    def _claim_validation_reason(
        self, claim_text: str, confidence: float
    ) -> str | None:
        if len(claim_text.split()) < 12:
            return "claim_too_short"
        if confidence < 0.5:
            return "low_confidence"
        lowered = claim_text.lower()
        if any(pattern in lowered for pattern in HEDGING_PATTERNS):
            return "hedging_only"
        return None

    def _heuristic_claim(self, paper: Paper, context: ProviderContext) -> PaperClaim:
        abstract = re.sub(r"\s+", " ", (paper.abstract or "").strip())
        sentences = [
            segment.strip()
            for segment in re.split(r"(?<=[.!?])\s+", abstract)
            if segment.strip()
        ]
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
                    "no effect",
                ]
            )
        ]
        chosen = (
            prioritized[0]
            if prioritized
            else (sentences[-1] if sentences else paper.title)
        )
        population = self._infer_population(paper)
        outcome = self._infer_outcome(paper, chosen)
        direction = self._detect_direction(chosen)
        magnitude = self._detect_magnitude(chosen)
        confidence = (
            0.72 if chosen != paper.title and len(chosen.split()) >= 12 else 0.45
        )
        return PaperClaim(
            paper_id=paper.id,
            provider=context.normalized_provider,
            model=context.model,
            found=True,
            claim=chosen,
            direction=direction,
            magnitude=magnitude,
            population=population,
            outcome=outcome,
            confidence=confidence,
            quality=confidence,
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
        outcome_similarity = jaccard_similarity(claim_a.outcome, claim_b.outcome)
        direction_conflict = (
            claim_a.direction != claim_b.direction
            and ClaimDirection.null
            not in {
                claim_a.direction,
                claim_b.direction,
            }
        )
        null_involved = ClaimDirection.null in {claim_a.direction, claim_b.direction}
        raw_score = 0.15
        contradiction_type: ContradictionType | None = ContradictionType.null
        explanation = "Findings are compatible or address different measurements."
        is_contradiction = False
        could_both_be_true = True
        key_difference = "different context"

        if direction_conflict and outcome_similarity >= 0.2:
            raw_score = 0.82
            contradiction_type = ContradictionType.direct
            explanation = (
                "The findings target similar outcomes but point in opposite directions."
            )
            is_contradiction = True
            could_both_be_true = False
            key_difference = "opposite effect direction"
        elif null_involved and outcome_similarity >= 0.2:
            raw_score = 0.58
            contradiction_type = ContradictionType.conditional
            explanation = "One study reports a directional effect while the other reports a null finding."
            key_difference = "null versus directional"
        elif outcome_similarity >= 0.2:
            raw_score = 0.3
            contradiction_type = ContradictionType.methodological
            explanation = (
                "The findings are related but do not cleanly reverse one another."
            )
            key_difference = "method variation"

        return ContradictionPair(
            paper_a_id=paper_a.id,
            paper_b_id=paper_b.id,
            mode=ContradictionMode.corpus_vs_corpus,
            provider=context.normalized_provider,
            model=context.model,
            raw_score=raw_score,
            score=raw_score,
            type=contradiction_type,
            explanation=explanation,
            is_contradiction=is_contradiction,
            could_both_be_true=could_both_be_true,
            key_difference=key_difference,
            paper_a_claim=claim_a.claim,
            paper_b_claim=claim_b.claim,
            paper_a=paper_a,
            paper_b=paper_b,
            raw={"mode": "heuristic"},
        )

    def _heuristic_input_claims(self, best_section: str) -> list[InputClaim]:
        sentences = [
            re.sub(r"\s+", " ", sentence.strip())
            for sentence in re.split(r"(?<=[.!?])\s+", best_section)
            if len(sentence.strip().split()) >= 10
        ]
        claims: list[InputClaim] = []
        seen_queries: set[str] = set()
        for sentence in sentences:
            direction = self._detect_direction(sentence)
            query_tokens = list(
                tokenize_text(sentence, drop_stop_words=True, min_length=3)
            )[:6]
            search_query = " ".join(query_tokens[:6]).strip()
            if not search_query or search_query in seen_queries:
                continue
            seen_queries.add(search_query)
            claims.append(
                InputClaim(
                    claim=sentence,
                    direction=direction,
                    search_query=search_query,
                    population=None,
                    outcome=" ".join(query_tokens[:4]) or None,
                )
            )
            if len(claims) == 5:
                break
        return claims

    @staticmethod
    def _detect_direction(text: str) -> ClaimDirection:
        lowered = text.lower()
        negative_markers = [
            "no significant",
            "no benefit",
            "no measurable",
            "did not",
            "not associated",
            "without effect",
            "failed to",
            "ineffective",
            "no effect",
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

    @staticmethod
    def _detect_magnitude(text: str) -> ClaimMagnitude:
        lowered = text.lower()
        if any(
            marker in lowered
            for marker in ["strong", "marked", "substantial", "dramatic"]
        ):
            return ClaimMagnitude.strong
        if any(
            marker in lowered for marker in ["moderate", "significant", "meaningful"]
        ):
            return ClaimMagnitude.moderate
        if any(marker in lowered for marker in ["small", "slight", "weak"]):
            return ClaimMagnitude.weak
        return ClaimMagnitude.null

    @staticmethod
    def _infer_population(paper: Paper) -> str | None:
        source = " ".join([paper.title, paper.abstract or ""]).lower()
        if (
            "mouse" in source
            or "mice" in source
            or "rat" in source
            or "animal" in source
        ):
            return "animal"
        if "in vitro" in source or "cell line" in source:
            return "in vitro"
        if "children" in source or "adolescent" in source or "pediatric" in source:
            return "pediatric"
        if "elderly" in source or "older adults" in source:
            return "elderly"
        if "healthy" in source:
            return "healthy"
        if "patients" in source or "disease" in source:
            return "patient"
        if "adult" in source or "human" in source or "participants" in source:
            return "human"
        return None

    @staticmethod
    def _infer_outcome(paper: Paper, sentence: str) -> str | None:
        keyword_candidates = [paper.outcome, *paper.keywords, *paper.mesh_terms]
        for candidate in keyword_candidates:
            if candidate:
                tokens = list(tokenize_text(candidate, drop_stop_words=True))
                if tokens:
                    return " ".join(tokens[:4])
        tokens = [
            token
            for token in tokenize_text(sentence, drop_stop_words=True)
            if token not in tokenize_text(paper.title, drop_stop_words=True)
        ]
        if tokens:
            return " ".join(list(tokens)[:4])
        return None
