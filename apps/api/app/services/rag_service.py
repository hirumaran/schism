import logging
import os
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

async def search_youtube_videos(queries: list[str]) -> list[dict]:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    results = []
    
    if api_key:
        url = "https://www.googleapis.com/youtube/v3/search"
        async with httpx.AsyncClient(timeout=8.0) as client:
            for query in queries:
                try:
                    response = await client.get(
                        url,
                        params={
                            "part": "snippet",
                            "type": "video",
                            "maxResults": 3,
                            "relevanceLanguage": "en",
                            "q": query,
                            "key": api_key,
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("items", []):
                            snippet = item.get("snippet", {})
                            video_id = item.get("id", {}).get("videoId")
                            if not video_id:
                                continue
                            results.append({
                                "title": snippet.get("title", ""),
                                "channel": snippet.get("channelTitle", ""),
                                "video_id": video_id,
                                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "description_snippet": snippet.get("description", ""),
                                "is_search_fallback": False
                            })
                except Exception as exc:
                    logger.warning("youtube_api_failed", extra={"error": str(exc), "query": query})
    
    if not results:
        for query in queries:
            encoded = urllib.parse.quote_plus(query)
            results.append({
                "title": query,
                "url": f"https://www.youtube.com/results?search_query={encoded}",
                "is_search_fallback": True
            })
            
    return results

async def search_web_resources(queries: list[str]) -> list[dict]:
    tavily_key = os.environ.get("TAVILY_API_KEY")
    serp_key = os.environ.get("SERPAPI_KEY")
    results = []
    
    if tavily_key:
        url = "https://api.tavily.com/search"
        async with httpx.AsyncClient(timeout=8.0) as client:
            for query in queries:
                try:
                    response = await client.post(
                        url,
                        json={"api_key": tavily_key, "query": query, "search_depth": "basic", "max_results": 3}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("results", []):
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "source_domain": urllib.parse.urlparse(item.get("url", "")).netloc,
                                "description_snippet": item.get("content", ""),
                                "is_search_fallback": False
                            })
                except Exception as exc:
                    logger.warning("tavily_api_failed", extra={"error": str(exc), "query": query})
    elif serp_key:
        url = "https://serpapi.com/search"
        async with httpx.AsyncClient(timeout=8.0) as client:
            for query in queries:
                try:
                    response = await client.get(
                        url,
                        params={"engine": "google", "q": query, "api_key": serp_key, "num": 3}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("organic_results", []):
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "source_domain": urllib.parse.urlparse(item.get("link", "")).netloc,
                                "description_snippet": item.get("snippet", ""),
                                "is_search_fallback": False
                            })
                except Exception as exc:
                    logger.warning("serp_api_failed", extra={"error": str(exc), "query": query})
                    
    if not results:
        for query in queries:
            encoded = urllib.parse.quote_plus(query)
            results.append({
                "title": query,
                "url": f"https://scholar.google.com/scholar?q={encoded}",
                "source_domain": "scholar.google.com",
                "description_snippet": "Search Google Scholar for academic papers",
                "is_search_fallback": True
            })
            
    return results
