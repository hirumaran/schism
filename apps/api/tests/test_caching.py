from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from app.config import Settings
from app.models.api import AnalyzeRequest
from app.models.claim import ClaimDirection, ClaimMagnitude, PaperClaim
from app.models.contradiction import ContradictionPair, ContradictionType
from app.models.paper import Paper
from app.models.report import AnalysisJob, ClaimCluster
from app.repositories.sqlite import SQLiteRepository
from app.services.contradiction_engine import ContradictionEngine
from app.services.embedding import EmbeddingService
from app.services.ingestion.service import IngestionService
from app.services.llm_client import LLMClient, ProviderContext
from app.services.vector_store import VectorStore


def build_service(tmp_path: Path) -> tuple[IngestionService, SQLiteRepository]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cache.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    service = IngestionService(
        user_agent=settings.user_agent,
        contact_email=settings.contact_email,
        repository=repository,
        settings=settings,
    )
    return service, repository


def make_paper(external_id: str) -> Paper:
    return Paper(
        source="stub",
        external_id=external_id,
        title="Omega 3 and cardiovascular risk",
        abstract=" ".join(["evidence"] * 100),
        year=2021,
        citation_count=10,
        keywords=["omega 3", "cardiovascular"],
    )


def test_query_cache_returns_cached_result_within_6_hours(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    paper = make_paper("a")
    client = type("Client", (), {"search": AsyncMock(return_value=[paper])})()
    service.clients = {"stub": client}

    first = asyncio.run(service.search("omega-3", ["stub"], 10))
    second = asyncio.run(service.search("omega-3", ["stub"], 10))

    assert first.papers
    assert second.papers
    assert client.search.await_count == 1


def test_query_cache_fetches_fresh_after_6_hours(tmp_path: Path) -> None:
    service, repository = build_service(tmp_path)
    paper = make_paper("a")
    client = type("Client", (), {"search": AsyncMock(return_value=[paper])})()
    service.clients = {"stub": client}

    asyncio.run(service.search("omega-3", ["stub"], 10))
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    with repository._connect() as connection:  # noqa: SLF001 - test-only direct DB update
        connection.execute("UPDATE query_cache SET created_at = ?", (stale_time,))
        connection.commit()

    asyncio.run(service.search("omega-3", ["stub"], 10))
    assert client.search.await_count == 2


def test_claim_cache_skips_llm_for_papers_with_existing_claims(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'claim-cache.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    llm_client = LLMClient(settings)
    llm_client.extract_claim = AsyncMock()
    paper = make_paper("a")
    repository.upsert_papers([paper])
    cached_claim = PaperClaim(
        paper_id=paper.id,
        provider="mock",
        found=True,
        claim="Omega 3 lowers cardiovascular risk markers in adults over time relative to control conditions",
        direction=ClaimDirection.positive,
        magnitude=ClaimMagnitude.moderate,
        outcome="cardiovascular risk markers",
        population="human",
        confidence=0.9,
        quality=0.9,
    )
    repository.save_claims([cached_claim])
    engine = ContradictionEngine(
        settings=settings,
        repository=repository,
        ingestion_service=type("Stub", (), {})(),  # type: ignore[arg-type]
        llm_client=llm_client,
        embedding_service=EmbeddingService(model_name=settings.local_embedding_model),
        vector_store=VectorStore(settings),
    )

    claims = asyncio.run(engine._extract_claims([paper], ProviderContext(provider="mock")))
    assert claims[0].claim == cached_claim.claim
    llm_client.extract_claim.assert_not_called()


def test_contradiction_cache_skips_llm_for_scored_pairs(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'contradiction-cache.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    llm_client = LLMClient(settings)
    llm_client.score_contradiction = AsyncMock()
    paper_a = make_paper("a")
    paper_b = make_paper("b")
    repository.upsert_papers([paper_a, paper_b])
    cached_pair = ContradictionPair(
        paper_a_id=paper_a.id,
        paper_b_id=paper_b.id,
        raw_score=0.7,
        score=0.7,
        type=ContradictionType.direct,
        explanation="cached",
        is_contradiction=True,
    )
    repository.save_contradiction(cached_pair)
    claim_a = PaperClaim(
        paper_id=paper_a.id,
        provider="mock",
        found=True,
        claim="Omega 3 lowers cardiovascular risk markers in adults over time relative to control conditions",
        direction=ClaimDirection.positive,
        outcome="cardiovascular risk markers",
        population="human",
        confidence=0.9,
        quality=0.9,
    )
    claim_b = PaperClaim(
        paper_id=paper_b.id,
        provider="mock",
        found=True,
        claim="Omega 3 has no effect on cardiovascular risk markers in adults over time relative to control conditions",
        direction=ClaimDirection.null,
        outcome="cardiovascular risk markers",
        population="human",
        confidence=0.9,
        quality=0.9,
    )
    engine = ContradictionEngine(
        settings=settings,
        repository=repository,
        ingestion_service=type("Stub", (), {})(),  # type: ignore[arg-type]
        llm_client=llm_client,
        embedding_service=EmbeddingService(model_name=settings.local_embedding_model),
        vector_store=VectorStore(settings),
    )
    contradictions, _, summary = asyncio.run(
        engine._score_clusters(
            job=AnalysisJob(query="omega-3"),
            request=AnalyzeRequest(query="omega-3"),
            context=ProviderContext(provider="mock"),
            papers=[paper_a, paper_b],
            claims=[claim_a, claim_b],
            clusters=[ClaimCluster(id="cluster_1", paper_ids=[paper_a.id, paper_b.id], claim_texts=["a", "b"], paper_count=2)],
        )
    )

    assert contradictions
    assert summary["cached_pairs"] == 1
    llm_client.score_contradiction.assert_not_called()
