import re
with open('apps/api/app/services/llm_client.py', 'r') as f:
    content = f.read()

from_import = "from app.models.report import PaperBreakdown, CoreConcept, SearchQueries"

if "PaperBreakdown" not in content:
    content = content.replace("from app.models.paper import ", "from app.models.report import PaperBreakdown, CoreConcept, SearchQueries\nfrom app.models.paper import ")

BREAKDOWN_SYSTEM_PROMPT = '''
BREAKDOWN_SYSTEM_PROMPT = """
You are a brilliant science communicator who explains complex research papers to smart but non-expert readers.
Your task is to break down a paper into clear, understandable components.
Rules:
- Start with the simplest possible explanation.
- Build up to technical depth.
- Never use undefined acronyms.
- Treat the reader as a smart non-expert.
Return valid JSON exactly matching the requested format.
""".strip()

BREAKDOWN_USER_PROMPT = """
Paper Title: {title}
Paper Abstract: {abstract}
Other Text: {full_text}

Generate a breakdown of this paper with:
- one_line_summary
- high_level_explanation (2-3 sentences, plain language, no jargon)
- core_concepts (3-5 concepts with name, plain_explanation, technical_explanation, why_it_matters)
- methodology_summary
- key_findings (3-5 bullet points)
- limitations (2-3 limitations the paper acknowledges or that are apparent)
- related_fields
- search_queries (with "youtube" x3 for explainers, "academic" x2-3 for related papers, "general" x2-3 for plain-language search)

Return ONLY JSON.
""".strip()
'''

BREAKDOWN_METHOD = '''
    async def generate_paper_breakdown(self, paper: Paper, context: ProviderContext) -> PaperBreakdown | None:
        if self._should_use_fallback(context):
            return None
        
        full_text = ""
        if hasattr(paper, "raw") and paper.raw and isinstance(paper.raw, dict):
            full_text = str(paper.raw.get("full_text", ""))[:4000]
        
        try:
            raw_content = await self.failover_invoke(
                system_prompt=BREAKDOWN_SYSTEM_PROMPT,
                user_prompt=BREAKDOWN_USER_PROMPT.format(
                    title=paper.title,
                    abstract=paper.abstract or "",
                    full_text=full_text,
                ),
                context=context,
            )
            result = parse_llm_json(raw_content, PaperBreakdown)
            if result:
                return PaperBreakdown.model_validate(result.model_dump())
        except Exception as exc:
            logger.warning("breakdown_generation_failed", extra={"error": str(exc)})
        return None
'''

if "BREAKDOWN_SYSTEM_PROMPT" not in content:
    content = content.replace("HEDGING_PATTERNS = [", BREAKDOWN_SYSTEM_PROMPT + "\n\nHEDGING_PATTERNS = [")

if "def generate_paper_breakdown" not in content:
    content = content.replace("    async def extract_claim(", BREAKDOWN_METHOD + "\n    async def extract_claim(")

with open('apps/api/app/services/llm_client.py', 'w') as f:
    f.write(content)
