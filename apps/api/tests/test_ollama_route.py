from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.main import app


class DummyResponse:
    def __init__(
        self, status_code: int, payload: object, *, json_error: bool = False
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self) -> object:
        if self._json_error:
            raise ValueError("invalid json")
        return self._payload


def make_async_client(
    *,
    response: DummyResponse | None = None,
    exc: Exception | None = None,
    capture: dict | None = None,
):
    class DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            if capture is not None:
                capture["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback) -> None:
            return None

        async def get(self, url: str, headers=None):
            if capture is not None:
                capture["url"] = url
                capture["headers"] = headers
            if exc is not None:
                raise exc
            assert response is not None
            return response

    return DummyAsyncClient


def test_ollama_tags_success_returns_sorted_models(monkeypatch) -> None:
    capture: dict[str, object] = {}
    monkeypatch.setattr(
        "app.routers.ollama.httpx.AsyncClient",
        make_async_client(
            response=DummyResponse(
                200,
                {
                    "models": [
                        {"name": "mistral"},
                        {"name": "llama3.1"},
                        {"name": "mistral"},
                        {"id": "missing-name"},
                    ]
                },
            ),
            capture=capture,
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/api/ollama/tags",
        json={"base_url": "https://ollama.com/api/", "api_key": "  cloud_key  "},
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["llama3.1", "mistral"]}
    assert capture["url"] == "https://ollama.com/api/tags"
    assert capture["headers"] == {"Authorization": "Bearer cloud_key"}


def test_ollama_tags_invalid_api_key_returns_401(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.ollama.httpx.AsyncClient",
        make_async_client(response=DummyResponse(401, {"detail": "unauthorized"})),
    )
    client = TestClient(app)

    response = client.post(
        "/api/ollama/tags",
        json={"base_url": "https://ollama.com", "api_key": "bad_key"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Ollama API key"


def test_ollama_tags_local_upstream_error_returns_502(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.ollama.httpx.AsyncClient",
        make_async_client(response=DummyResponse(503, {})),
    )
    client = TestClient(app)

    response = client.post(
        "/api/ollama/tags",
        json={"base_url": "http://localhost:11434"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Cannot connect to Ollama"


def test_ollama_tags_cloud_network_error_returns_502(monkeypatch) -> None:
    request = httpx.Request("GET", "https://ollama.com/api/tags")
    monkeypatch.setattr(
        "app.routers.ollama.httpx.AsyncClient",
        make_async_client(exc=httpx.ConnectError("network down", request=request)),
    )
    client = TestClient(app)

    response = client.post(
        "/api/ollama/tags",
        json={"base_url": "https://ollama.com", "api_key": "cloud_key"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Cannot reach Ollama Cloud"


def test_ollama_tags_invalid_json_returns_502(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.ollama.httpx.AsyncClient",
        make_async_client(response=DummyResponse(200, {}, json_error=True)),
    )
    client = TestClient(app)

    response = client.post(
        "/api/ollama/tags",
        json={"base_url": "http://localhost:11434"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Invalid response from Ollama"
