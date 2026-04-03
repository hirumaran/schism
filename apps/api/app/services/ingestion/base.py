from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import httpx

from app.models.paper import Paper


class RateLimiter:
    def __init__(self, concurrency: int, delay_seconds: float):
        self._semaphore = asyncio.Semaphore(concurrency)
        self._delay = delay_seconds

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *args):
        await asyncio.sleep(self._delay)
        self._semaphore.release()


class BaseIngester(ABC):
    source: str
    rate_limiter: RateLimiter

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[Paper]:
        raise NotImplementedError

    async def fetch_with_retry(self, client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt in range(3):
            async with self.rate_limiter:
                response = await client.get(url, **kwargs)
            last_response = response
            if response.status_code == 429:
                if attempt < 2:
                    await asyncio.sleep(float(2**attempt))
                    continue
                response.raise_for_status()
            if response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(1.0)
                    continue
                response.raise_for_status()
            response.raise_for_status()
            return response

        if last_response is not None:
            last_response.raise_for_status()
        raise httpx.HTTPStatusError("Request failed after retries.", request=None, response=None)
