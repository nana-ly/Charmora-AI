# Setup Guide

## Prerequisites

- Python 3.12
- uv
- Docker Desktop
- JDK 17
- Android Studio

## Backend

```powershell
cd backend
uv sync
Copy-Item .env.example .env
uv run fastapi dev main.py
```

Open:

```text
http://127.0.0.1:8000/docs
```

Run checks:

```powershell
cd backend
uv run pytest
uv run ruff check .
```

Agent Runner 配置：

```env
AGENT_RUNNER=langgraph
```

`langgraph` 是默认且唯一支持的模式。可以用下面的命令做联调前检查：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"session_id":"setup-check","message":"预算9000以内的拍照手机"}'
```

## Android

Android project files will live in `android/`.

Recommended local API base URLs:

```text
Android emulator: http://10.0.2.2:8000
Physical device: http://<computer-lan-ip>:8000
```

## GitHub

The repository is organized as a single monorepo from the project root. Do not create nested Git repositories inside `backend/` or `android/`.
