# Schism API

FastAPI backend for the Schism contradiction-detection workflow.

## Run locally

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[ml,dev]"
cp .env.example .env
python -m app.main
```

## Core endpoints

- `POST /api/search` searches arXiv, Semantic Scholar, OpenAlex, and PubMed in parallel.
- `POST /api/analyze` runs search or uses stored paper IDs, extracts claims, clusters them, and scores contradictions.
- `GET /api/reports/{report_id}` fetches a stored analysis report.
- `GET /api/reports/{report_id}/export?format=csv` exports contradiction rows.

## Provider header flow

The backend never stores user API keys. The frontend sends provider credentials on each request:

```http
POST /api/analyze
X-Provider: anthropic
X-Api-Key: sk-ant-...
X-Model: claude-3-5-sonnet-latest
```

`ollama` can be used without `X-Api-Key` when the backend can reach the local Ollama endpoint.
