# Schism

Find research papers that contradict each other - or contradict yours.

## What it does

Schism takes either a search query or your own research paper and finds published papers with conflicting conclusions. It surfaces direct contradictions, conditional contradictions (same question, different populations), and methodological differences.

## Two modes

**Query mode** - search by topic, find papers that contradict each other within that topic.

**Paper input mode** - paste your abstract or upload your PDF, find papers that contradict your specific claims.

## Quick start

```bash
bash apps/scripts/schism.sh
```

Backend: http://localhost:8000  
Frontend: http://localhost:3000

## Docker Quick start

```bash
cp apps/api/.env.example apps/api/.env
docker compose up
```

API runs at http://localhost:8000  
Docs at http://localhost:8000/docs

## Running the Project Locally

### Prerequisites

- Node.js 20+
- Python 3.12+
- `pip` and `venv`
- Optional: Docker and Docker Compose for the one-command stack

### Backend setup

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

The FastAPI backend runs at http://localhost:8000 and the OpenAPI docs are at http://localhost:8000/docs.

### Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The Next.js frontend runs at http://localhost:3000.

### Environment variables

Backend variables live in `apps/api/.env.example`:

- `PORT=8000`
- `FRONTEND_URL=http://localhost:3000`
- `SCHISM_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`

Frontend variables live in `frontend/.env.example`:

- `NEXT_PUBLIC_API_URL=/api`
- `SCHISM_API_PROXY_TARGET=http://localhost:8000`

In local development the frontend defaults to `/api` and Next.js rewrites those requests to the backend, so you do not need to hardcode `localhost:8000` in the browser.

### Docker option

```bash
cp apps/api/.env.example apps/api/.env
docker compose up --build
```

This starts the backend at http://localhost:8000 plus the supporting services defined in `docker-compose.yml`.

## API key setup

Schism never stores your API keys. Pass them per-request:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "X-Provider: anthropic" \
  -H "X-Api-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"query": "vitamin D depression", "max_results": 40}'
```

Supported providers: anthropic, openai, ollama (local, no key needed)

## Paper input example

```bash
curl -X POST http://localhost:8000/api/analyze/paper \
  -H "X-Provider: anthropic" \
  -H "X-Api-Key: sk-ant-..." \
  -F "file=@my_paper.pdf"
```

```bash
curl -X POST http://localhost:8000/api/analyze/paper \
  -H "X-Provider: anthropic" \
  -H "X-Api-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"text": "your abstract here..."}'
```

## Free paper sources

arXiv · Semantic Scholar · PubMed · OpenAlex - all free, no keys needed.
