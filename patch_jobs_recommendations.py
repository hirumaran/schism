import re
with open('apps/api/app/routers/jobs.py', 'r') as f:
    content = f.read()

recommendations_endpoint = """
from datetime import datetime, timezone
import asyncio
from app.services.rag_service import search_youtube_videos, search_web_resources
from pydantic import BaseModel

class RecommendationsResponse(BaseModel):
    videos: list[dict]
    web_resources: list[dict]
    generated_at: str

@router.get("/reports/{job_id}/recommendations", response_model=RecommendationsResponse)
async def get_report_recommendations(
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> RecommendationsResponse:
    report = service.repository.get_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    if report.recommendations_cache:
        return RecommendationsResponse.model_validate(report.recommendations_cache)
        
    if not report.paper_breakdown:
        return RecommendationsResponse(videos=[], web_resources=[], generated_at=datetime.now(timezone.utc).isoformat())

    queries = report.paper_breakdown.search_queries
    youtube_queries = queries.youtube
    academic_general_queries = queries.academic + queries.general
    
    videos = []
    web_resources = []
    try:
        videos_task = asyncio.create_task(search_youtube_videos(youtube_queries))
        web_task = asyncio.create_task(search_web_resources(academic_general_queries))
        done, pending = await asyncio.wait([videos_task, web_task], timeout=8.0)
        
        if videos_task in done and not videos_task.exception():
            videos = videos_task.result()
        if web_task in done and not web_task.exception():
            web_resources = web_task.result()
            
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("recommendations_failed", extra={"error": str(exc)})
        
    response = RecommendationsResponse(
        videos=videos,
        web_resources=web_resources,
        generated_at=datetime.now(timezone.utc).isoformat()
    )
    
    report.recommendations_cache = response.model_dump(mode="json")
    service.repository.save_report(report)
    
    return response

"""

if "get_report_recommendations" not in content:
    content = content + "\n" + recommendations_endpoint

with open('apps/api/app/routers/jobs.py', 'w') as f:
    f.write(content)
