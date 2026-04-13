---
# Schism

Find research papers that contradict each other —
or contradict yours.

## What it does

Schism takes a research topic or your own paper and
finds published papers with conflicting conclusions.

- **Direct** — same population, same outcome,
  opposite result
- **Conditional** — same question, different
  conditions or subgroups lead to opposite findings
- **Methodological** — same question, different
  methodology leads to different conclusions

## Two modes

**Query mode** — enter a topic. Schism searches
arXiv, Semantic Scholar, PubMed, and OpenAlex,
extracts the main claim from each paper, clusters
them by subtopic, and surfaces pairs with
contradictory conclusions.

**Paper mode** — paste your abstract or upload a
PDF. Schism extracts your specific claims and finds
published papers that directly contradict each one.
Useful before submission.

## Quick start

### With Docker

  cp apps/api/.env.example apps/api/.env
  docker compose up

Backend: http://localhost:8000
Frontend: http://localhost:3000
API docs: http://localhost:8000/docs

### Without Docker

  # Terminal 1 — backend
  cd apps/api
  python -m venv .venv
  source .venv/bin/activate
  pip install -e ".[ml]"
  uvicorn app.main:app --reload --port 8000

  # Terminal 2 — frontend
  cd frontend
  npm install
  npm run dev

### One command (local dev)

  bash apps/scripts/schism.sh

## API keys

Schism never stores your API keys on any server.
Keys are saved in your browser's localStorage and
injected per-request. Open Settings in the top-right
corner to configure your provider.

| Provider  | Notes                              |
|-----------|------------------------------------|
| Anthropic | Recommended. claude-sonnet-4-6     |
| OpenAI    | Good alternative. gpt-4o-mini      |
| Ollama    | Local, free, private. No key needed|
| Mock      | No key. Heuristic results only     |

## Paper sources

All sources are free — no API keys required.

| Source           | Coverage                        |
|------------------|---------------------------------|
| arXiv            | Preprints — CS, physics, bio    |
| Semantic Scholar | 200M+ papers, all fields        |
| PubMed           | Biomedical, NIH indexed         |
| OpenAlex         | Broad coverage, open access     |

## Environment variables

Copy apps/api/.env.example to apps/api/.env

| Variable                      | Default        | Description                  |
|-------------------------------|----------------|------------------------------|
| SCHISM_DATABASE_URL           | sqlite:///...  | Database path                |
| SCHISM_ENABLE_QDRANT          | false          | Enable vector store          |
| SCHISM_QDRANT_URL             | localhost:6333 | Qdrant URL                   |
| SCHISM_CONTRADICTION_THRESHOLD| 0.6            | Min score to surface pairs   |
| SCHISM_JOB_TIMEOUT_MINUTES    | 15             | Max job duration             |
| SCHISM_QUERY_CACHE_HOURS      | 6              | Cache raw API results        |
| SCHISM_ANALYSIS_CACHE_HOURS   | 24             | Cache full analyses          |

## Troubleshooting

**Cannot reach backend**
Make sure uvicorn is running on port 8000.
Check SCHISM_API_PROXY_TARGET in frontend/.env.local.

**No results found**
Try a more specific query. Increase max papers.
Add more sources. The threshold is 0.6 — pairs
below this are filtered out.

**LLM provider error**
Your API key may be invalid or rate-limited.
Open Settings and use the Validate button.

**PDF extraction failed**
Some PDFs are scanned images with no selectable
text. Paste the abstract manually instead.

**Ollama not connecting**
Run: ollama serve
Check the base URL in Settings matches your setup.
Pull the model first: ollama pull llama3