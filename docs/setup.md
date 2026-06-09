# Setup Guide

## Prerequisites

- Python 3.12
- uv
- Docker Desktop（可选；当前本地代码路径不强依赖 Docker）
- JDK 17
- Android Studio

## Backend

```powershell
cd backend
uv sync
Copy-Item .env.example .env
uv run fastapi dev main.py
```

默认 `.env.example` 使用 `RETRIEVER_MODE=vector`。vector 模式需要本地 Chroma 索引和 `embedding_api` 可用；只做离线联调时，可以先把 `backend/.env` 改为：

```env
RETRIEVER_MODE=keyword
```

如需构建向量索引，先在 `rag/` 目录配置 embedding 后执行：

```powershell
cd rag
uv sync
uv run python -m shopguide_rag.cli index
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

Android 原生客户端位于 `android/`。当前客户端默认通过 Retrofit 调用 `POST /chat`，并优先使用 `POST /chat/stream` 的 SSE 流式响应；当 SSE 接口不可用时会回退到 REST `/chat`。

Recommended local API base URLs:

```text
Android emulator: http://10.0.2.2:8000
Physical device: http://<computer-lan-ip>:8000
```

Android 端的语音识别凭证从 `android/.env` 注入到 `BuildConfig`，字段名为：

```env
BAIDU_APP_ID=
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
```

## GitHub

The repository is organized as a single monorepo from the project root. Do not create nested Git repositories inside `backend/` or `android/`.
