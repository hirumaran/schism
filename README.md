# Schism

Find research papers that contradict each other - or contradict yours.

## What it does

Schism takes either a search query or your own research paper and finds published papers with conflicting conclusions. It surfaces direct contradictions, conditional contradictions (same question, different populations), and methodological differences.

## Two modes

**Query mode** - search by topic, find papers that contradict each other within that topic.

**Paper input mode** - paste your abstract or upload your PDF, find papers that contradict your specific claims.

## Quick start

```bash
cp apps/api/.env.example apps/api/.env
docker compose up
```

API runs at http://localhost:8000  
Docs at http://localhost:8000/docs

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
