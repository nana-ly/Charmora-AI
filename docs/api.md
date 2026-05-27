# ShopGuide RAG API 接口契约

本文档固定 ShopGuide RAG 的 HTTP 接口、字段边界和错误语义。客户端可以依赖这里列出的字段；后端可以新增可选字段，但不应删除或改名既有字段。

## 本地地址

```text
http://127.0.0.1:8000
```

## 接口清单

```http
GET  /
GET  /health
POST /recommend
POST /rag/search
POST /chat
POST /chat/stream
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

## Recommend

`POST /recommend` 执行单轮商品推荐。

Request:

```json
{
  "query": "预算9000以内，想买拍照和剪视频好的手机"
}
```

Response:

```json
{
  "query": "预算9000以内，想买拍照和剪视频好的手机",
  "filters": {
    "category": "数码电子",
    "max_price": 9000,
    "brand": null,
    "keywords": ["手机", "拍照", "剪视频"]
  },
  "items": [
    {
      "product_id": "p_digital_001",
      "title": "Apple iPhone 17 Pro",
      "brand": "Apple",
      "price": 8999,
      "reason": "这款商品与需求匹配，命中拍照和视频相关证据。",
      "evidence": "临时匹配：命中 手机、拍照、剪视频；来自结构化筛选结果。"
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `query` | `string` | 原样返回用户输入，便于调试和展示。 |
| `filters.category` | `string \| null` | 后端解析出的商品品类。 |
| `filters.max_price` | `number \| null` | 后端解析出的最高预算。 |
| `filters.brand` | `string \| null` | 后端解析出的品牌偏好。 |
| `filters.keywords` | `string[]` | 后端从 query 中命中的关键词。 |
| `items` | `array` | 推荐商品列表；没有匹配时返回空数组。 |
| `items[].product_id` | `string` | 商品唯一 ID。 |
| `items[].title` | `string` | 商品名称。 |
| `items[].brand` | `string` | 商品品牌。 |
| `items[].price` | `number` | 商品价格。 |
| `items[].reason` | `string` | 中文推荐理由。 |
| `items[].evidence` | `string` | 中文匹配依据。 |

推荐链路不会为无结果或异常伪造商品。检索结果为空时 `items` 是 `[]`；推荐链路异常时异常向上暴露。

## RAG Search

`POST /rag/search` 用于本地调试向量召回质量。

Request:

```json
{
  "query": "适合熬夜后修护的抗初老精华",
  "top_k": 5
}
```

Response:

```json
{
  "query": "适合熬夜后修护的抗初老精华",
  "items": [
    {
      "product_id": "p_beauty_001",
      "title": "修护精华",
      "brand": "测试品牌",
      "score": 0.82,
      "evidence": "向量召回：相似度 0.82 ..."
    }
  ]
}
```

## Chat

`POST /chat` 执行一轮多轮导购对话。

Request:

```json
{
  "session_id": "demo-session",
  "message": "预算9000以内的拍照手机"
}
```

Response:

```json
{
  "session_id": "demo-session",
  "reply": "我根据你的需求筛选了这几款商品，可以先看第一款的匹配理由。",
  "items": [],
  "state": {
    "intent": "recommend",
    "preferences": {
      "category": "数码电子",
      "max_price": 9000,
      "keywords": ["手机", "拍照"]
    }
  }
}
```

`state.intent` 当前取值：

```text
recommend
update_preference
explain
clarify
```

## Chat Stream

`POST /chat/stream` 复用 `/chat` 请求体，用 SSE 返回事件。

正常事件顺序：

```text
start -> delta -> items -> state -> done
```

进入流式处理后的业务异常事件顺序：

```text
start -> error -> done
```

请求体验证失败仍由 FastAPI 返回 `422`，不会进入 SSE 流。

## 后端推荐链路

```text
api.recommend
  -> services.recommendation_service.run_recommendation
  -> services.retriever_factory.select_retriever
  -> recommendation_core.pipeline.recommend_products
  -> Retriever.search
  -> recommendation_core.response_builder.build_response_item
  -> return {"query", "filters", "items"}
```

`choose_candidates()` 严格使用结构化条件。`RETRIEVER_MODE=vector` 使用向量检索并暴露向量错误；`RETRIEVER_MODE=keyword` 使用关键词检索。
