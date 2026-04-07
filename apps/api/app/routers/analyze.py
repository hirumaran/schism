from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile

from app.dependencies import (
    get_analysis_service,
    get_paper_input_parser,
    get_provider_context,
)
from app.models.api import (
    AnalyzeAcceptedResponse,
    AnalyzePaperTextRequest,
    AnalyzeRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.llm_client import ProviderContext
from app.services.paper_input import PaperInputParser

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeAcceptedResponse, status_code=202)
async def analyze_papers(
    request: AnalyzeRequest,
    response: Response,
    service: AnalysisService = Depends(get_analysis_service),
    provider_context: ProviderContext = Depends(get_provider_context),
) -> AnalyzeAcceptedResponse:
    job, cache_state, status_code = await service.run_analysis(
        request=request, context=provider_context
    )
    response.status_code = status_code
    if cache_state is not None:
        response.headers["X-Cache"] = cache_state
    return AnalyzeAcceptedResponse(job_id=job.id, status=job.status)


@router.post("/analyze/paper", response_model=AnalyzeAcceptedResponse, status_code=202)
async def analyze_paper(
    request: Request,
    response: Response,
    service: AnalysisService = Depends(get_analysis_service),
    provider_context: ProviderContext = Depends(get_provider_context),
    parser: PaperInputParser = Depends(get_paper_input_parser),
) -> AnalyzeAcceptedResponse:
    content_type = request.headers.get("content-type", "").lower()

    try:
        if "application/json" in content_type:
            payload = AnalyzePaperTextRequest.model_validate(await request.json())
            parsed_input = await parser.parse_text(payload.text, payload.title)
            sections = parser.extract_sections(parsed_input.text)
            job, cache_state, status_code = await service.run_paper_analysis(
                parsed_input=parsed_input,
                sections=sections,
                max_results=payload.max_results,
                sources=payload.sources,
                context=provider_context,
            )
        elif "multipart/form-data" in content_type:
            form = await request.form()
            upload = form.get("file")
            has_file_attrs = hasattr(upload, "filename") and hasattr(upload, "read")
            if upload is None or not has_file_attrs:
                raise ValueError("Missing file upload.")
            max_results = int(form.get("max_results", 50))
            sources_raw = str(form.get("sources", "arxiv,semantic_scholar"))
            title = form.get("title") or None
            parsed_input = await parser.parse_upload(upload, title=title)
            sections = parser.extract_sections(parsed_input.text)
            job, cache_state, status_code = await service.run_paper_analysis(
                parsed_input=parsed_input,
                sections=sections,
                max_results=max_results,
                sources=[
                    source.strip()
                    for source in sources_raw.split(",")
                    if source.strip()
                ],
                context=provider_context,
            )
        else:
            raise ValueError("Use either application/json or multipart/form-data.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.status_code = status_code
    if cache_state is not None:
        response.headers["X-Cache"] = cache_state
    return AnalyzeAcceptedResponse(job_id=job.id, status=job.status)
