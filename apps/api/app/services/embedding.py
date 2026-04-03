from __future__ import annotations

import asyncio
import hashlib
import math
import re
from typing import Any

BATCH_SIZE = 64


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

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

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
