from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from app.models.api import OllamaTagsRequest, OllamaTagsResponse

router = APIRouter(tags=["ollama"])


def _tags_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise HTTPException(status_code=400, detail="Ollama base URL is required.")
    if normalized.endswith("/api/tags"):
        return normalized
    if normalized.endswith("/api"):
        return f"{normalized}/tags"
    return f"{normalized}/api/tags"


@router.post("/ollama/tags", response_model=OllamaTagsResponse)
async def get_ollama_tags(request: OllamaTagsRequest) -> OllamaTagsResponse:
    url = _tags_url(request.base_url)
    api_key = (request.api_key or "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0)
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Cannot reach Ollama Cloud"
            if api_key
            else "Cannot connect to Ollama",
        ) from exc

    if api_key and response.status_code in {401, 403}:
        raise HTTPException(status_code=401, detail="Invalid Ollama API key")

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail="Cannot reach Ollama Cloud"
            if api_key
            else "Cannot connect to Ollama",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="Invalid response from Ollama"
        ) from exc

    models_raw = payload.get("models", []) if isinstance(payload, dict) else []
    models = sorted(
        {
            model.get("name")
            for model in models_raw
            if isinstance(model, dict) and isinstance(model.get("name"), str)
        }
    )

    return OllamaTagsResponse(models=models)
