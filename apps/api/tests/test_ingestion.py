from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.models.paper import Paper
from app.repositories.sqlite import SQLiteRepository
from app.services.ingestion.service import IngestionService


def build_service(tmp_path: Path) -> IngestionService:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'ingestion.db'}")
    return IngestionService(
        user_agent=settings.user_agent,
        contact_email=settings.contact_email,
        repository=SQLiteRepository(settings.sqlite_path),
        settings=settings,
    )


def test_abstract_quality_filter_removes_short_abstracts(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    paper = Paper(source="stub", external_id="a", title="Valid title", abstract="Too short abstract.", year=2020)
    filtered = service._apply_quality_filters([paper])
    assert filtered == []


def test_title_deduplication_catches_near_duplicate_titles(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    left = Paper(
        source="stub",
        external_id="a",
        title="Omega 3 and cardiovascular risks",
        abstract=" ".join(["word"] * 100),
        year=2020,
    )
    right = Paper(
        source="stub",
        external_id="b",
        title="Omega-3 and cardiovascular risk",
        abstract=" ".join(["word"] * 120),
        year=2020,
    )
    deduped, removed = service._dedupe([left, right])
    assert len(deduped) == 1
    assert removed == 1


def test_year_filter_removes_pre_1990_papers(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    paper = Paper(source="stub", external_id="a", title="Old paper", abstract=" ".join(["word"] * 100), year=1985)
    filtered = service._apply_quality_filters([paper])
    assert filtered == []


def test_retracted_paper_filter_works(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    paper = Paper(source="stub", external_id="a", title="Retracted: omega 3 trial", abstract=" ".join(["word"] * 100), year=2020)
    filtered = service._apply_quality_filters([paper])
    assert filtered == []
