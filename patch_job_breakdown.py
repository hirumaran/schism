import re
with open('apps/api/app/services/contradiction_engine.py', 'r') as f:
    content = f.read()

# I want to add analysis_job.paper_breakdown = paper_breakdown right before await self._complete_job(analysis_job, report...)
content = re.sub(
    r'(paper_breakdown = [^\n]+\n(?:[ \t]+except[^\n]+\n[ \t]+logger\.warning[^\n]+\n)*\s+report = AnalysisReport\()',
    r'\1',
    content
)
# Wait, let's just do it directly.
content = content.replace("await self._complete_job(analysis_job, report, has_contradictions=False)", "analysis_job.paper_breakdown = paper_breakdown\n                await self._complete_job(analysis_job, report, has_contradictions=False)")
content = content.replace("await self._complete_job(analysis_job, report, has_contradictions=has_contradictions)", "analysis_job.paper_breakdown = paper_breakdown\n                await self._complete_job(analysis_job, report, has_contradictions=has_contradictions)")

with open('apps/api/app/services/contradiction_engine.py', 'w') as f:
    f.write(content)
