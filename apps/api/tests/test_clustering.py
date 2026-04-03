from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.models.paper import Paper
from app.repositories.sqlite import SQLiteRepository
from app.services.contradiction_engine import ContradictionEngine
from app.services.embedding import EmbeddingService
from app.services.ingestion.service import IngestionService
from app.services.llm_client import LLMClient
from app.services.vector_store import VectorStore


class EmptyIngestionService:
    async def search(self, query, sources, max_results):
        raise AssertionError("search should not be called")


def build_engine(tmp_path: Path) -> ContradictionEngine:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cluster.db'}")
    return ContradictionEngine(
        settings=settings,
        repository=SQLiteRepository(settings.sqlite_path),
        ingestion_service=EmptyIngestionService(),  # type: ignore[arg-type]
        llm_client=LLMClient(settings),
        embedding_service=EmbeddingService(model_name=settings.local_embedding_model),
        vector_store=VectorStore(settings),
    )


def make_papers(count: int) -> list[Paper]:
    return [
        Paper(
            source="stub",
            external_id=f"paper-{index}",
            title=f"Omega 3 cardiovascular effect paper {index}",
            abstract=(
                "Omega 3 cardiovascular outcomes are discussed with repeated evidence about inflammation, "
                "lipids, vascular function, mortality, and biomarkers across a large abstract body."
            ),
            citation_count=100 - index,
            year=2010 + (index % 10),
            keywords=["omega 3", "cardiovascular", "lipids"],
        )
        for index in range(count)
    ]


def test_fallback_clustering_triggers_when_hdbscan_returns_single_cluster(tmp_path: Path, monkeypatch) -> None:
    engine = build_engine(tmp_path)
    papers = make_papers(4)
    embeddings = [[1.0, 0.0, 0.0] for _ in papers]
    monkeypatch.setattr(engine, "_cluster_with_hdbscan", lambda papers, embeddings: [])

    clusters = engine._cluster_papers(papers, embeddings)
    assert clusters
    assert any(cluster.fallback_used for cluster in clusters)


def test_cluster_size_cap_trims_to_20_papers_by_citation_count(tmp_path: Path, monkeypatch) -> None:
    engine = build_engine(tmp_path)
    papers = make_papers(25)
    embeddings = [[1.0, 0.0, 0.0] for _ in papers]
    monkeypatch.setattr(engine, "_cluster_with_hdbscan", lambda papers, embeddings: [])

    clusters = engine._cluster_papers(papers, embeddings)
    assert clusters
    assert clusters[0].paper_count == 20
    assert clusters[0].trimmed_count == 5


def test_cluster_metadata_top_terms_returns_five_terms(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    papers = make_papers(5)
    top_terms = engine._top_terms(papers)
    assert len(top_terms) == 5
