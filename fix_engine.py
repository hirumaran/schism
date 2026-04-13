with open('apps/api/app/services/contradiction_engine.py', 'r') as f:
    content = f.read()

# Make sure paper_breakdown is initialized before AnalysisReport
# And passed inside AnalysisReport
import re

def fix_report_calls(text):
    # Find all AnalysisReport(...) blocks
    blocks = []
    pattern = re.compile(r'(paper_breakdown = .*?report = AnalysisReport\()(.*?)\)', re.DOTALL | re.MULTILINE)
    
    # Actually just add paper_breakdown=paper_breakdown at the end of kwargs before )
    text = re.sub(r'paper_breakdown=paper_breakdown,\s*paper_breakdown=paper_breakdown,', 'paper_breakdown=paper_breakdown,', text)
    return text

content = fix_report_calls(content)
with open('apps/api/app/services/contradiction_engine.py', 'w') as f:
    f.write(content)
