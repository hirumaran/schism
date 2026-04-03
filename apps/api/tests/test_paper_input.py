from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import UploadFile

from app.config import Settings
from app.models.claim import ClaimDirection, InputClaim, PaperClaim
from app.models.contradiction import ContradictionMode, ContradictionPair, ContradictionType
from app.models.paper import Paper
from app.models.report import AnalysisJob, ClaimCluster
from app.repositories.sqlite import SQLiteRepository
from app.services.contradiction_engine import ContradictionEngine
from app.services.embedding import EmbeddingService
from app.services.ingestion.service import IngestionResult
from app.services.llm_client import LLMClient, ProviderContext
from app.services.paper_input import PaperInputParser
from app.services.vector_store import VectorStore


class StubIngestionService:
    async def search(self, query: str, sources: list[str], max_results: int) -> IngestionResult:
        raise AssertionError("ingestion should not be called in these tests")


def build_engine(tmp_path: Path, llm_client: LLMClient | None = None) -> ContradictionEngine:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'paper-input.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    return ContradictionEngine(
        settings=settings,
        repository=repository,
        ingestion_service=StubIngestionService(),  # type: ignore[arg-type]
        llm_client=llm_client or LLMClient(settings),
        embedding_service=EmbeddingService(model_name=settings.local_embedding_model),
        vector_store=VectorStore(settings),
    )


def make_paper(external_id: str, title: str) -> Paper:
    return Paper(
        source="stub",
        external_id=external_id,
        title=title,
        abstract=" ".join(["evidence"] * 120),
        year=2023,
    )


def test_parse_pdf_upload(monkeypatch) -> None:
    parser = PaperInputParser()

    class FakePage:
        def extract_text(self):
            return "This PDF contains a long abstract with enough extracted text to be useful. " * 5

    class FakeReader:
        def __init__(self, stream):
            self.pages = [FakePage()]

    monkeypatch.setattr("app.services.paper_input.PdfReader", FakeReader, raising=False)
    upload = UploadFile(filename="paper.pdf", file=BytesIO(b"%PDF-1.4 mock"))
    parsed = asyncio.run(parser.parse_upload(upload))
    assert parsed.filename == "paper.pdf"
    assert parsed.text


def test_parse_text_input() -> None:
    parser = PaperInputParser()
    parsed = asyncio.run(parser.parse_text(" ".join(["abstract"] * 30), "Example"))
    assert parsed.title == "Example"
    assert parsed.text.startswith("abstract")


def test_extract_sections_with_abstract() -> None:
    parser = PaperInputParser()
    sections = parser.extract_sections("Abstract\nThis is the abstract text.\n\nMethods\nMethod text.")
    assert sections.abstract == "This is the abstract text."
    assert sections.best_section == "This is the abstract text."


def test_extract_sections_conclusion_fallback() -> None:
    parser = PaperInputParser()
    sections = parser.extract_sections("Introduction\nLead in.\n\nConclusion\nThis is the conclusion text.")
    assert sections.conclusion == "This is the conclusion text."
    assert sections.best_section == "This is the conclusion text."


def test_extract_sections_full_text_fallback() -> None:
    parser = PaperInputParser()
    text = " ".join(["fulltext"] * 600)
    sections = parser.extract_sections(text)
    assert sections.best_section == text[:3000]


def test_input_claims_extraction(tmp_path: Path) -> None:
    client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'llm.db'}"))
    client._invoke_text = AsyncMock(  # type: ignore[method-assign]
        return_value='{"claims":[{"claim":"Omega 3 reduces cardiovascular risk in adults over time","direction":"positive","search_query":"omega 3 cardiovascular risk","population":"adult humans","outcome":"cardiovascular risk"}]}'
    )
    claims = asyncio.run(client.extract_input_claims("Input section text", ProviderContext(provider="anthropic", api_key="key")))
    assert len(claims) == 1
    assert claims[0].search_query == "omega 3 cardiovascular risk"
    assert claims[0].outcome == "cardiovascular risk"


def test_paper_vs_corpus_scoring(tmp_path: Path) -> None:
    llm_client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'score.db'}"))
    llm_client.score_contradiction = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda claim_a, claim_b, paper_a, paper_b, context: ContradictionPair(
            paper_a_id=paper_a.id,
            paper_b_id=paper_b.id,
            mode=ContradictionMode.paper_vs_corpus,
            raw_score=0.8,
            score=0.8,
            type=ContradictionType.direct,
            explanation="Conflicting claims.",
            is_contradiction=True,
            paper_a_claim=claim_a.claim,
            paper_b_claim=claim_b.claim,
        )
    )
    engine = build_engine(tmp_path, llm_client=llm_client)
    input_paper = Paper(
        id="input_job_x",
        source="user_input",
        external_id="job_x",
        title="User paper",
        abstract=" ".join(["claim"] * 100),
    )
    input_claims = [
        InputClaim(
            claim="Omega 3 reduces cardiovascular risk in adults over time",
            direction=ClaimDirection.positive,
            search_query="omega 3 cardiovascular risk",
            population="human",
            outcome="cardiovascular risk",
        ),
        InputClaim(
            claim="Omega 3 lowers inflammatory markers in adults over time",
            direction=ClaimDirection.positive,
            search_query="omega 3 inflammatory markers",
            population="human",
            outcome="inflammatory markers",
        ),
    ]
    fetched_papers = [
        make_paper("a", "Paper A"),
        make_paper("b", "Paper B"),
        make_paper("c", "Paper C"),
    ]
    engine.repository.upsert_papers([input_paper, *fetched_papers])
    fetched_claims = [
        PaperClaim(
            paper_id=fetched_papers[0].id,
            provider="mock",
            found=True,
            claim="Omega 3 has no effect on cardiovascular risk in adults over time",
            direction=ClaimDirection.null,
            population="human",
            outcome="cardiovascular risk",
            confidence=0.9,
            quality=0.9,
        ),
        PaperClaim(
            paper_id=fetched_papers[1].id,
            provider="mock",
            found=True,
            claim="Omega 3 increases inflammatory markers in adults over time",
            direction=ClaimDirection.negative,
            population="human",
            outcome="inflammatory markers",
            confidence=0.9,
            quality=0.9,
        ),
        PaperClaim(
            paper_id=fetched_papers[2].id,
            provider="mock",
            found=True,
            claim="Omega 3 worsens cardiovascular risk in adults over time",
            direction=ClaimDirection.negative,
            population="human",
            outcome="cardiovascular risk",
            confidence=0.9,
            quality=0.9,
        ),
    ]
    clusters = [ClaimCluster(id="cluster_1", paper_ids=[paper.id for paper in fetched_papers], claim_texts=["a", "b", "c"], paper_count=3)]
    job = AnalysisJob(query="User paper", mode=ContradictionMode.paper_vs_corpus)

    contradictions, _, _ = asyncio.run(
        engine._score_input_claims(
            job=job,
            context=ProviderContext(provider="mock"),
            input_paper=input_paper,
            input_claims=input_claims,
            fetched_papers=fetched_papers,
            fetched_claims=fetched_claims,
            clusters=clusters,
        )
    )

    assert contradictions
    assert all(pair.paper_a_id == input_paper.id for pair in contradictions)
    assert all(pair.paper_b_id != input_paper.id for pair in contradictions)
