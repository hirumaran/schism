import re

with open("frontend/app/reports/[id]/page.tsx", "r") as f:
    content = f.read()

content = content.replace(
    '<h2 className="font-serif text-2xl mb-3">No results found</h2>',
    '<h2 className="font-serif text-2xl mb-3">Analysis Complete</h2>',
)
content = content.replace(
    "The analyzed papers did not contain significant contradictions. Run analysis again to see a detailed paper breakdown.",
    "Run analysis again to see a detailed paper breakdown for this job.",
)

with open("frontend/app/reports/[id]/page.tsx", "w") as f:
    f.write(content)
