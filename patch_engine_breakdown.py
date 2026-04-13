with open('apps/api/app/services/contradiction_engine.py', 'r') as f:
    content = f.read()

# In analyze_paper, right before saving the report
analyze_paper_breakdown = """
            paper_breakdown = None
            try:
                paper_breakdown = await self.llm_client.generate_paper_breakdown(input_paper, context)
            except Exception as exc:
                logger.warning("breakdown_failed", extra={"error": str(exc)})
            
            report = AnalysisReport(
"""

content = content.replace("            report = AnalysisReport(", analyze_paper_breakdown)

# In analyze, right before saving the report
analyze_breakdown = """
            paper_breakdown = None
            if papers:
                try:
                    paper_breakdown = await self.llm_client.generate_paper_breakdown(papers[0], context)
                except Exception as exc:
                    logger.warning("breakdown_failed", extra={"error": str(exc)})
            
            report = AnalysisReport(
"""

content = content.replace("            report = AnalysisReport(", analyze_breakdown, 1) # Only first match for analyze, wait the replace above already replaced both?

# Let's undo and be precise
with open('apps/api/app/services/contradiction_engine.py', 'w') as f:
    f.write(content)
