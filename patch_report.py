with open('apps/api/app/models/report.py', 'r') as f:
    content = f.read()

paper_breakdown_classes = """
class CoreConcept(BaseModel):
    name: str
    plain_explanation: str
    technical_explanation: str
    why_it_matters: str

class SearchQueries(BaseModel):
    youtube: list[str]
    academic: list[str]
    general: list[str]

class PaperBreakdown(BaseModel):
    one_line_summary: str
    high_level_explanation: str
    core_concepts: list[CoreConcept]
    methodology_summary: str
    key_findings: list[str]
    limitations: list[str]
    related_fields: list[str]
    search_queries: SearchQueries
"""

if "class CoreConcept(BaseModel):" not in content:
    content = content.replace("class AnalysisJob(BaseModel):", paper_breakdown_classes + "\nclass AnalysisJob(BaseModel):")

if "paper_breakdown: PaperBreakdown | None = None" not in content:
    content = content.replace("    has_contradictions: bool = False\n", "    has_contradictions: bool = False\n    paper_breakdown: PaperBreakdown | None = None\n")

if "recommendations_cache: dict[str, object] | None = None" not in content:
    content = content.replace("    has_contradictions: bool = False\n", "    has_contradictions: bool = False\n    recommendations_cache: dict[str, object] | None = None\n")

with open('apps/api/app/models/report.py', 'w') as f:
    f.write(content)
