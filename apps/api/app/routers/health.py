from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_embedding_service, get_vector_store
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck(
    settings: Settings = Depends(get_settings),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "embedding_backend": embedding_service.backend_name(),
        "vector_store": vector_store.health(),
        "supported_sources": ["arxiv", "semantic_scholar", "openalex", "pubmed"],
        "supported_providers": ["mock", "openai", "anthropic", "ollama"],
    }

