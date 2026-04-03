from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import Settings
from app.models.api import AnalyzeRequest
from app.models.paper import Paper
from app.repositories.sqlite import SQLiteRepository
from app.services.contradiction_engine import ContradictionEngine
from app.services.embedding import EmbeddingService
from app.services.ingestion.service import IngestionResult
from app.services.llm_client import LLMClient, ProviderContext
from app.services.vector_store import VectorStore


class StubIngestionService:
    async def search(self, query: str, sources: list[str], max_results: int) -> IngestionResult:
        return IngestionResult(
            papers=[
                Paper(
                    source="stub",
                    external_id="paper-a",
                    title="Vitamin D improves depressive symptoms in adults",
                    abstract=(
                        "In this randomized trial, vitamin D supplementation significantly improved "
                        "depressive symptoms in adults with deficiency. The intervention reduced symptom scores."
                    ),
                    keywords=["vitamin d", "depression"],
                ),
                Paper(
                    source="stub",
                    external_id="paper-b",
                    title="Vitamin D has no measurable effect on depression outcomes",
                    abstract=(
                        "In this controlled trial, vitamin D supplementation did not improve "
                        "depressive symptoms and was not associated with lower depression scores."
                    ),
                    keywords=["vitamin d", "depression"],
                ),
            ][:max_results],
            warnings=[],
        )


def test_mock_pipeline_detects_a_contradiction(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'schism-test.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    engine = ContradictionEngine(
        settings=settings,
        repository=repository,
        ingestion_service=StubIngestionService(),
        llm_client=LLMClient(settings),
        embedding_service=EmbeddingService(model_name=settings.local_embedding_model),
        vector_store=VectorStore(settings),
    )

    report = asyncio.run(
        engine.analyze(
            request=AnalyzeRequest(
                query="vitamin d depression",
                sources=["stub"],
                max_results=2,
                min_keyword_overlap=1,
                contradiction_threshold=0.6,
            ),
            context=ProviderContext(provider="mock"),
        )
    )

    assert len(report.claims) == 2
    assert len(report.clusters) >= 1
    assert report.contradictions
    assert report.contradictions[0].is_contradiction is True
    assert report.contradictions[0].score >= 0.6

