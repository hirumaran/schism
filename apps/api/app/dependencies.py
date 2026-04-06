from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from app.config import Settings, get_settings
from app.repositories.sqlite import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.contradiction_engine import ContradictionEngine
from app.services.embedding import EmbeddingService
from app.services.ingestion.service import IngestionService
from app.services.llm_client import LLMClient, ProviderContext
from app.services.paper_input import PaperInputParser
from app.services.report_exporter import ReportExporter
from app.services.vector_store import VectorStore


@lru_cache
def get_repository() -> SQLiteRepository:
    settings = get_settings()
    return SQLiteRepository(settings.sqlite_path)


@lru_cache
def get_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(
        user_agent=settings.user_agent,
        contact_email=settings.contact_email,
        repository=get_repository(),
        settings=settings,
    )


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(model_name=settings.local_embedding_model)


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(get_settings())


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient(get_settings())


@lru_cache
def get_report_exporter() -> ReportExporter:
    return ReportExporter()


@lru_cache
def get_paper_input_parser() -> PaperInputParser:
    return PaperInputParser()


@lru_cache
def get_contradiction_engine() -> ContradictionEngine:
    settings: Settings = get_settings()
    return ContradictionEngine(
        settings=settings,
        repository=get_repository(),
        ingestion_service=get_ingestion_service(),
        llm_client=get_llm_client(),
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
    )


@lru_cache
def get_analysis_service() -> AnalysisService:
    settings = get_settings()
    return AnalysisService(
        settings=settings,
        repository=get_repository(),
        engine=get_contradiction_engine(),
    )


def get_provider_context(request: Request) -> ProviderContext:
    return ProviderContext(
        provider=request.headers.get("X-Provider", "mock"),
        api_key=request.headers.get("X-Api-Key"),
        model=request.headers.get("X-Model"),
        base_url=request.headers.get("X-Base-Url"),
        embedding_provider=request.headers.get("X-Embedding-Provider"),
        embedding_api_key=request.headers.get("X-Embedding-Api-Key"),
    )
