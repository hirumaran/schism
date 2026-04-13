import re
with open('frontend/lib/types.ts', 'r') as f:
    content = f.read()

new_types = """
export interface CoreConcept {
  name: string
  plain_explanation: string
  technical_explanation: string
  why_it_matters: string
}

export interface SearchQueries {
  youtube: string[]
  academic: string[]
  general: string[]
}

export interface PaperBreakdown {
  one_line_summary: string
  high_level_explanation: string
  core_concepts: CoreConcept[]
  methodology_summary: string
  key_findings: string[]
  limitations: string[]
  related_fields: string[]
  search_queries: SearchQueries
}
"""

if "export interface PaperBreakdown" not in content:
    content = content.replace("export interface Paper {", new_types + "\nexport interface Paper {")

# Update ContradictionPair
if "claim_a_text:" not in content:
    content = content.replace("  cluster_id: string | null\n}", "  cluster_id: string | null\n  claim_a_text: string | null\n  claim_b_text: string | null\n  paper_a_title: string\n  paper_b_title: string\n  contradiction_score: number\n  contradiction_type: string\n}")

# Update Report
if "paper_breakdown?:" not in content:
    content = content.replace("  input_paper?: {", "  paper_breakdown?: PaperBreakdown | null\n  input_paper?: {")

with open('frontend/lib/types.ts', 'w') as f:
    f.write(content)
