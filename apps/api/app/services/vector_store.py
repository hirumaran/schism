from __future__ import annotations

from typing import Any

from app.config import Settings
from app.models.claim import PaperClaim


class VectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any | None = None
        self._collection_ready = False
        self._last_error: str | None = None

    def health(self) -> dict[str, Any]:
        if not self.settings.enable_qdrant:
            return {
                "enabled": False,
                "backend": "local",
                "collection": self.settings.qdrant_collection,
            }
        return {
            "enabled": True,
            "backend": "qdrant",
            "collection": self.settings.qdrant_collection,
            "ready": self._client is not None or self._collection_ready,
            "last_error": self._last_error,
        }

    def upsert_claims(self, claims: list[PaperClaim], embeddings: list[list[float]]) -> None:
        if not self.settings.enable_qdrant or not claims or not embeddings:
            return

        try:
            client = self._get_client()
            if client is None:
                return

            from qdrant_client.http import models as qmodels

            self._ensure_collection(client, len(embeddings[0]))
            points = [
                qmodels.PointStruct(
                    id=claim.paper_id,
                    vector=embedding,
                    payload={
                        "paper_id": claim.paper_id,
                        "provider": claim.provider,
                        "model": claim.model,
                        "claim": claim.claim,
                        "quality": claim.quality,
                    },
                )
                for claim, embedding in zip(claims, embeddings, strict=False)
            ]
            client.upsert(collection_name=self.settings.qdrant_collection, points=points)
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client

        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.settings.qdrant_url, timeout=5.0)
        except Exception as exc:
            self._last_error = str(exc)
            self._client = None
        return self._client

    def _ensure_collection(self, client: Any, dimensions: int) -> None:
        if self._collection_ready:
            return

        from qdrant_client.http import models as qmodels

        collections = client.get_collections().collections
        names = {collection.name for collection in collections}
        if self.settings.qdrant_collection not in names:
            client.create_collection(
                collection_name=self.settings.qdrant_collection,
                vectors_config=qmodels.VectorParams(size=dimensions, distance=qmodels.Distance.COSINE),
            )
        self._collection_ready = True

