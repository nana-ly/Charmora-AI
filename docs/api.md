# API Draft

Base URL for local development:

```text
http://127.0.0.1:8000
```

## Health

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

## Root

```http
GET /
```

Response:

```json
{
  "name": "ShopGuide RAG API",
  "status": "running"
}
```

## Planned MVP APIs

```http
POST /api/chat
POST /api/chat/stream
POST /api/images/upload
GET  /api/products/{product_id}
POST /api/knowledge/documents/upload
POST /api/knowledge/index
POST /api/feedback
```

