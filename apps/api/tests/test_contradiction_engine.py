from __future__ import annotations

import asyncio
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
from app.services.ingestion.service import IngestionResult
from app.services.llm_client import LLMClient, ProviderContext
from app.services.vector_store import VectorStore


class StubIngestionService:
    def __init__(self, papers: list[Paper]) -> None:
        self._papers = papers

    async def search(self, query: str, sources: list[str], max_results: int) -> IngestionResult:
        return IngestionResult(
            papers=self._papers[:max_results],
            warnings=[],
            sources_searched=sources,
        )


def make_paper(external_id: str, title: str, *, year: int = 2020, citation_count: int = 10, population: str | None = None) -> Paper:
    directional_sentence = (
        "Omega 3 supplementation did not improve cardiovascular biomarkers and was not associated with lower risk over follow-up."
        if "no " in title.lower() or "no cardiovascular benefit" in title.lower() or "shows no" in title.lower()
        else "Omega 3 supplementation improved cardiovascular biomarkers and reduced cardiovascular risk over follow-up."
    )
    abstract = (
        f"{title}. This randomized study reports a clear empirical finding with substantial detail about "
        f"the measured outcome and repeated evidence across participants. {directional_sentence} "
        f"Additional analysis documented cardiovascular biomarkers, inflammatory markers, lipid measures, "
        f"vascular function, adverse events, and compliance outcomes across baseline and longitudinal visits. "
        f"The abstract further explains subgroup consistency, sensitivity analyses, comparative controls, "
        f"and outcome stability over time to ensure the word count comfortably exceeds the extraction threshold."
    )
    return Paper(
        source="stub",
        external_id=external_id,
        title=title,
        abstract=abstract,
        year=year,
        citation_count=citation_count,
        keywords=["omega 3", "cardiovascular"],
        population=population,
    )


def make_claim(
    paper_id: str,
    *,
    claim: str,
    direction: ClaimDirection,
    outcome: str,
    population: str | None = "human",
) -> PaperClaim:
    return PaperClaim(
        paper_id=paper_id,
        provider="mock",
        found=True,
        claim=claim,
        direction=direction,
        magnitude=ClaimMagnitude.moderate,
        outcome=outcome,
        population=population,
        confidence=0.9,
        quality=0.9,
    )


def build_engine(tmp_path: Path, llm_client: LLMClient | None = None, papers: list[Paper] | None = None) -> ContradictionEngine:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'schism-test.db'}")
    repository = SQLiteRepository(settings.sqlite_path)
    return ContradictionEngine(
        settings=settings,
        repository=repository,
        ingestion_service=StubIngestionService(papers or []),
        llm_client=llm_client or LLMClient(settings),
        embedding_service=EmbeddingService(model_name=settings.local_embedding_model),
        vector_store=VectorStore(settings),
    )


def test_mock_pipeline_detects_a_contradiction(tmp_path: Path) -> None:
    papers = [
        make_paper(
            "paper-a",
            "Omega-3 supplementation improves cardiovascular biomarkers and vascular outcomes in adults over follow-up",
        ),
        make_paper(
            "paper-b",
            "Omega-3 supplementation shows no cardiovascular benefit or biomarker improvement in adults over follow-up",
        ),
    ]
    llm_client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'llm.db'}"))
    llm_client.extract_claim = AsyncMock(
        side_effect=[
            make_claim(
                papers[0].id,
                claim="Omega 3 supplementation improves cardiovascular biomarkers and vascular outcomes in adults over follow-up",
                direction=ClaimDirection.positive,
                outcome="cardiovascular biomarkers",
            ),
                make_claim(
                    papers[1].id,
                    claim="Omega 3 supplementation worsens cardiovascular biomarkers in adults over follow-up",
                    direction=ClaimDirection.negative,
                    outcome="cardiovascular biomarkers",
                ),
            ]
        )
    engine = build_engine(tmp_path, llm_client=llm_client, papers=papers)
    report = asyncio.run(
        engine.analyze(
            request=AnalyzeRequest(
                query="omega-3 cardiovascular",
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


def test_direction_filter_skips_same_direction_pairs(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    paper_a = make_paper("a", "A")
    paper_b = make_paper("b", "B")
    claim_a = make_claim(paper_a.id, claim="omega 3 reduces blood pressure in adults over time", direction=ClaimDirection.positive, outcome="blood pressure")
    claim_b = make_claim(paper_b.id, claim="omega 3 lowers blood pressure in adults during follow up", direction=ClaimDirection.positive, outcome="blood pressure")

    result = engine._prefilter_pair(claim_a, claim_b, paper_a, paper_b, min_keyword_overlap=1)
    assert result["action"] == "skip"


def test_outcome_filter_skips_low_jaccard_pairs(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    paper_a = make_paper("a", "A")
    paper_b = make_paper("b", "B")
    claim_a = make_claim(paper_a.id, claim="omega 3 reduces blood pressure in adults over time", direction=ClaimDirection.positive, outcome="blood pressure")
    claim_b = make_claim(paper_b.id, claim="omega 3 changes memory retention in adults over time", direction=ClaimDirection.negative, outcome="memory retention")

    result = engine._prefilter_pair(claim_a, claim_b, paper_a, paper_b, min_keyword_overlap=1)
    assert result["action"] == "skip"


def test_population_filter_tags_incompatible_populations_as_methodological(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    paper_a = make_paper("a", "A", population="human")
    paper_b = make_paper("b", "B", population="animal")
    claim_a = make_claim(paper_a.id, claim="omega 3 reduces blood pressure in human patients over time", direction=ClaimDirection.positive, outcome="blood pressure", population="human")
    claim_b = make_claim(paper_b.id, claim="omega 3 raises blood pressure in animal models over time", direction=ClaimDirection.negative, outcome="blood pressure", population="animal")

    result = engine._prefilter_pair(claim_a, claim_b, paper_a, paper_b, min_keyword_overlap=1)
    assert result["action"] == "methodological"
    pair = result["pair"]
    assert isinstance(pair, ContradictionPair)
    assert pair.type == ContradictionType.methodological
    assert pair.score == 0.3


def test_year_gap_penalty_is_applied_correctly(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    paper_a = make_paper("a", "A", year=2000)
    paper_b = make_paper("b", "B", year=2020)
    pair = ContradictionPair(
        paper_a_id=paper_a.id,
        paper_b_id=paper_b.id,
        raw_score=0.8,
        score=0.8,
        type=ContradictionType.direct,
        explanation="x",
        is_contradiction=True,
    )

    penalized = engine._apply_year_penalty(pair, paper_a, paper_b)
    assert penalized.raw_score == 0.8
    assert penalized.score == 0.65
    assert penalized.score_penalty == 0.15


def test_score_deduplication_keeps_higher_score(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    repo = engine.repository
    paper_a = make_paper("a", "A")
    paper_b = make_paper("b", "B")
    repo.upsert_papers([paper_a, paper_b])
    low = ContradictionPair(
        paper_a_id=paper_a.id,
        paper_b_id=paper_b.id,
        raw_score=0.4,
        score=0.4,
        type=ContradictionType.conditional,
        explanation="low",
        is_contradiction=False,
    )
    high = low.model_copy(update={"raw_score": 0.8, "score": 0.8, "type": ContradictionType.direct, "is_contradiction": True})
    repo.save_contradiction(low)
    repo.save_contradiction(high)

    stored = repo.get_cached_contradiction(paper_a.id, paper_b.id)
    assert stored is not None
    assert stored.score == 0.8
    assert stored.type == ContradictionType.direct


def test_claim_quality_gate_rejects_short_claim(tmp_path: Path) -> None:
    client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}"))
    claim = PaperClaim(
        paper_id="paper_x",
        provider="mock",
        found=True,
        claim="Omega 3 helps outcomes",
        direction=ClaimDirection.positive,
        confidence=0.9,
        quality=0.9,
    )
    finalized = client._finalize_claim(claim)
    assert finalized.claim is None
    assert finalized.skip_reason == "claim_too_short"


def test_claim_quality_gate_rejects_hedge_only_claim(tmp_path: Path) -> None:
    client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}"))
    claim = PaperClaim(
        paper_id="paper_x",
        provider="mock",
        found=True,
        claim="This paper investigates omega 3 effects in adults and suggests further research is needed",
        direction=ClaimDirection.null,
        confidence=0.9,
        quality=0.9,
    )
    finalized = client._finalize_claim(claim)
    assert finalized.claim is None
    assert finalized.skip_reason == "hedging_only"


def test_contradiction_cache_skips_llm(tmp_path: Path) -> None:
    llm_client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}"))
    llm_client.score_contradiction = AsyncMock()
    engine = build_engine(tmp_path, llm_client=llm_client)
    repo = engine.repository
    paper_a = make_paper("a", "A")
    paper_b = make_paper("b", "B")
    repo.upsert_papers([paper_a, paper_b])
    cached = ContradictionPair(
        paper_a_id=paper_a.id,
        paper_b_id=paper_b.id,
        raw_score=0.9,
        score=0.9,
        type=ContradictionType.direct,
        explanation="cached",
        is_contradiction=True,
    )
    repo.save_contradiction(cached)
    claim_a = make_claim(paper_a.id, claim="omega 3 reduces cardiovascular mortality in adults substantially over time", direction=ClaimDirection.positive, outcome="cardiovascular mortality")
    claim_b = make_claim(paper_b.id, claim="omega 3 has no effect on cardiovascular mortality in adults over time", direction=ClaimDirection.null, outcome="cardiovascular mortality")
    cluster = ClaimCluster(id="cluster_1", paper_ids=[paper_a.id, paper_b.id], claim_texts=["a", "b"], paper_count=2)
    job = AnalysisJob(query="omega-3 cardiovascular")

    contradictions, _, summary = asyncio.run(
        engine._score_clusters(
            job=job,
            request=AnalyzeRequest(query="omega-3 cardiovascular"),
            context=ProviderContext(provider="mock"),
            papers=[paper_a, paper_b],
            claims=[claim_a, claim_b],
            clusters=[cluster],
        )
    )

    assert contradictions
    assert summary["cached_pairs"] == 1
    llm_client.score_contradiction.assert_not_called()


def test_claim_cache_skips_llm(tmp_path: Path) -> None:
    llm_client = LLMClient(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}"))
    llm_client.extract_claim = AsyncMock()
    paper = make_paper("a", "Omega-3 improves endothelial function in adults")
    engine = build_engine(tmp_path, llm_client=llm_client)
    engine.repository.upsert_papers([paper])
    cached_claim = make_claim(
        paper.id,
        claim="Omega 3 improves endothelial function in adults over time compared with control treatment",
        direction=ClaimDirection.positive,
        outcome="endothelial function",
    )
    engine.repository.save_claims([cached_claim])

    claims = asyncio.run(engine._extract_claims([paper], ProviderContext(provider="mock")))
    assert claims[0].claim == cached_claim.claim
    llm_client.extract_claim.assert_not_called()
