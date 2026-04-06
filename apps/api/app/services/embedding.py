from __future__ import annotations

import asyncio
import hashlib
import math
import re
from typing import Any

import httpx

from app.models.paper import Paper

BATCH_SIZE = 64
OPENAI_BATCH_SIZE = 2048


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
    numerator = sum(left * right for left, right in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(value * value for value in vector_a))
    norm_b = math.sqrt(sum(value * value for value in vector_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return numerator / (norm_a * norm_b)


class EmbeddingService:
    def __init__(self, model_name: str, fallback_dimensions: int = 128) -> None:
        self.model_name = model_name
        self.fallback_dimensions = fallback_dimensions
        self._model: Any | None = None
        self._load_attempted = False

    def backend_name(self) -> str:
        return "sentence-transformers" if self._load_sentence_transformer() is not None else "hashing"

    async def embed_papers_with_cache(
        self,
        papers: list[Paper],
        vector_store: Any | None,  # VectorStore, may be None if Qdrant disabled
    ) -> list[list[float]]:
        """Embed papers with caching via vector store."""
        embeddings: list[tuple[int, list[float]]] = []
        papers_to_embed: list[Paper] = []
        paper_indices: list[int] = []

        for i, paper in enumerate(papers):
            if paper.embedding_id and vector_store:
                try:
                    # VectorStore.get_vector is synchronous, run in executor
                    loop = asyncio.get_running_loop()
                    cached = await loop.run_in_executor(None, vector_store.get_vector, paper.embedding_id)
                    if cached is not None:
                        embeddings.append((i, cached))
                        continue
                except Exception:
                    pass
            papers_to_embed.append(paper)
            paper_indices.append(i)

        if papers_to_embed:
            texts = [
                f"{p.title}. {p.abstract or ''}"[:512]
                for p in papers_to_embed
            ]
            new_embeddings = await self.embed_texts(texts)
            for idx, (paper, emb) in enumerate(
                zip(papers_to_embed, new_embeddings)
            ):
                embeddings.append((paper_indices[idx], emb))

        embeddings.sort(key=lambda x: x[0])
        return [emb for _, emb in embeddings]

    async def embed_texts(
        self,
        texts: list[str],
        provider: str = "local",
        api_key: str | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []

        if provider == "openai" and api_key:
            return await self._embed_texts_openai(texts, api_key)
        elif provider == "cohere" and api_key:
            return await self._embed_texts_cohere(texts, api_key)
        else:
            return await self._embed_texts_local(texts)

    async def _embed_texts_openai(
        self,
        texts: list[str],
        api_key: str,
    ) -> list[list[float]]:
        """Call OpenAI embeddings API."""
        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(texts), OPENAI_BATCH_SIZE):
                batch = texts[i : i + OPENAI_BATCH_SIZE]
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "text-embedding-3-small",
                        "input": batch,
                    },
                )

                if response.status_code == 401:
                    raise ValueError("Invalid OpenAI API key")
                elif response.status_code == 429:
                    raise ValueError("OpenAI rate limit exceeded")
                response.raise_for_status()

                data = response.json()["data"]
                # Sort by index to maintain order
                batch_embeddings = [
                    item["embedding"] for item in sorted(data, key=lambda x: x["index"])
                ]
                all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _embed_texts_cohere(
        self,
        texts: list[str],
        api_key: str,
    ) -> list[list[float]]:
        """Call Cohere embed API."""
        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(texts), BATCH_SIZE):
                batch = texts[i : i + BATCH_SIZE]
                response = await client.post(
                    "https://api.cohere.ai/v1/embed",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "embed-english-v3.0",
                        "texts": batch,
                        "input_type": "search_document",
                    },
                )

                if response.status_code == 401:
                    raise ValueError("Invalid Cohere API key")
                response.raise_for_status()

                result = response.json()
                all_embeddings.extend(result["embeddings"])

        return all_embeddings

    async def _embed_texts_local(self, texts: list[str]) -> list[list[float]]:
        """Local embedding using sentence-transformers or hashing fallback."""
        model = self._load_sentence_transformer()
        if model is not None:
            all_embeddings: list[list[float]] = []
            loop = asyncio.get_running_loop()
            for index in range(0, len(texts), BATCH_SIZE):
                batch = texts[index : index + BATCH_SIZE]
                batch_embeddings = await loop.run_in_executor(
                    None,
                    lambda b=batch: model.encode(b, normalize_embeddings=True).tolist(),
                )
                all_embeddings.extend([[float(value) for value in row] for row in batch_embeddings])
            return all_embeddings

        return [self._hash_embedding(text) for text in texts]

    def _load_sentence_transformer(self) -> Any | None:
        if self._load_attempted:
            return self._model

        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, local_files_only=True)
        except Exception:
            self._model = None
        return self._model

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.fallback_dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            index = digest[0] % self.fallback_dimensions
            sign = 1.0 if digest[1] % 2 else -1.0
            weight = 1.0 + (digest[2] / 255.0)
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
