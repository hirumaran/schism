# Schism

Schism is a contradiction-detection backend for research papers. This repository currently includes the full FastAPI flow: ingestion, claim extraction, clustering, contradiction scoring, report persistence, and export.

## Layout

```text
schism/
├── apps/
│   └── api/
│       ├── app/
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
└── docker-compose.yml
```

## Quick start

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000` with docs at `http://localhost:8000/docs`.
