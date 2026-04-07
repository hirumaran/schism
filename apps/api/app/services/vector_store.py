from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


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

    async def get_vector(self, embedding_id: str | None) -> list[float] | None:
        if not self.settings.enable_qdrant or not embedding_id:
            return None

        try:
            client = self._get_client()
            if client is None:
                return None
            await self._ensure_collection(client, 384)
            loop = asyncio.get_event_loop()
            points = await loop.run_in_executor(
                None, lambda: client.retrieve(collection_name=self.settings.qdrant_collection, ids=[embedding_id], with_vectors=True)
            )
            if not points:
                return None
            vector = points[0].vector
            if isinstance(vector, list):
                return [float(value) for value in vector]
        except Exception as exc:
            self._last_error = str(exc)
            logger.debug("vector_fetch_failed", extra={"embedding_id": embedding_id, "error": str(exc)})
        return None

    async def upsert_embeddings(self, points: list[dict[str, Any]], dimensions: int) -> None:
        if not self.settings.enable_qdrant or not points:
            return

        try:
            client = self._get_client()
            if client is None:
                return

            from qdrant_client.http import models as qmodels

            await self._ensure_collection(client, dimensions)
            payload = [
                qmodels.PointStruct(
                    id=point["id"],
                    vector=point["vector"],
                    payload=point.get("payload", {}),
                )
                for point in points
            ]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: client.upsert(collection_name=self.settings.qdrant_collection, points=payload)
            )
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("vector_upsert_failed", extra={"error": str(exc)})

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

    async def _ensure_collection(self, client: Any, dimensions: int) -> None:
        if self._collection_ready:
            return

        from qdrant_client.http import models as qmodels

        loop = asyncio.get_event_loop()
        collections = await loop.run_in_executor(None, client.get_collections)
        names = {collection.name for collection in collections.collections}
        if self.settings.qdrant_collection not in names:
            await loop.run_in_executor(
                None,
                lambda: client.create_collection(
                    collection_name=self.settings.qdrant_collection,
                    vectors_config=qmodels.VectorParams(size=dimensions, distance=qmodels.Distance.COSINE),
                ),
            )
        self._collection_ready = True
