from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_contradiction_engine, get_provider_context
from app.models.api import AnalyzeRequest, AnalyzeResponse
from app.services.contradiction_engine import ContradictionEngine
from app.services.llm_client import ProviderContext

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_papers(
    request: AnalyzeRequest,
    engine: ContradictionEngine = Depends(get_contradiction_engine),
    provider_context: ProviderContext = Depends(get_provider_context),
) -> AnalyzeResponse:
    report = await engine.analyze(request=request, context=provider_context)
    return AnalyzeResponse.model_validate(report.model_dump())

