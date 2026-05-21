# ShopGuide RAG

RAG-based multimodal ecommerce shopping guide AI Agent.

## Structure

```text
ShopGuide-RAG/
├─ android/                  # Native Android client
├─ backend/                  # FastAPI backend service
├─ docs/                     # Project docs, API docs, setup guide
├─ ecommerce_agent_dataset/  # Product dataset
├─ eval/                     # Evaluation datasets and scripts
└─ scripts/                  # Project helper scripts
```

## Quick Start

Backend:

```powershell
cd backend
uv sync
uv run fastapi dev main.py
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Run checks:

```powershell
cd backend
uv run pytest
uv run ruff check .
```

## Docs

- [Setup guide](docs/setup.md)
- [API draft](docs/api.md)
- [Project brief](docs/项目说明.md)
- [Android MVP plan](docs/Android原生3天最小闭环方案.md)

