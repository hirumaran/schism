with open('apps/api/app/services/contradiction_engine.py', 'r') as f:
    content = f.read()

content = content.replace("""                key_difference="population mismatch",
                paper_a_claim=claim_a.claim,
                paper_b_claim=claim_b.claim,
                raw={"mode": "prefilter"},""", """                key_difference="population mismatch",
                paper_a_claim=claim_a.claim,
                paper_b_claim=claim_b.claim,
                paper_a=paper_a,
                paper_b=paper_b,
                raw={"mode": "prefilter"},""")

content = content.replace("""                key_difference="population mismatch",
                paper_a_claim=input_claim.claim,
                paper_b_claim=fetched_claim.claim,
                raw={"mode": "prefilter"},""", """                key_difference="population mismatch",
                paper_a_claim=input_claim.claim,
                paper_b_claim=fetched_claim.claim,
                paper_a=input_paper,
                paper_b=fetched_paper,
                raw={"mode": "prefilter"},""")

with open('apps/api/app/services/contradiction_engine.py', 'w') as f:
    f.write(content)
