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

## Android

Android project files will live in `android/`.

Recommended local API base URLs:

```text
Android emulator: http://10.0.2.2:8000
Physical device: http://<computer-lan-ip>:8000
```

## GitHub

The repository is organized as a single monorepo from the project root. Do not create nested Git repositories inside `backend/` or `android/`.

