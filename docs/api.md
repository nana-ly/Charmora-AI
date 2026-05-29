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
  "items": [
    {
      "product_id": "p_digital_001",
      "title": "Apple iPhone 17 Pro",
      "brand": "Apple",
      "price": 8999,
      "reason": "这款商品与需求匹配，命中拍照相关证据。",
      "evidence": "命中关键词：手机、拍照。"
    }
  ],
  "state": {
    "intent": "recommend",
    "action": "recommend",
    "confidence": 0.9,
    "purchase_need": "预算9000以内的拍照手机",
    "preferences": {
      "category": "数码电子",
      "max_price": 9000,
      "keywords": ["手机", "拍照"]
    },
    "result_status": "success"
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

`state.action` 当前取值：

```text
recommend
explain
clarify
```

`state.result_status` 只描述本轮推荐执行结果，当前取值：

```text
success
no_results
tool_error
```

`state` 还可能包含这些可选字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `excluded_product_ids` | `string[]` | 当前购买上下文中被用户明确排除的商品 ID，例如“不要第 2 个”。 |
| `excluded_brands` | `string[]` | 当前购买上下文中被用户明确排除的品牌，例如“不要苹果”。 |
| `latest_attempt_status` | `"success" \| "no_results" \| "tool_error" \| null` | 最近一次推荐尝试状态，随当前购买上下文归档和恢复。 |
| `negative_feedback` | `object` | 本轮识别到负反馈时返回的应用结果，可能包含 `applied`、`removed`、`noop`、`needs_clarification`、`changed_fields`、`target_product_ids`、`target_brands`、`noop_reason` 等字段。 |

无结果响应仍保持 `items=[]`，并可能在 `state.relax_options` 中返回可放宽的条件。推荐工具异常会返回稳定对话响应，而不是伪造商品：

```json
{
  "session_id": "demo-session",
  "reply": "推荐服务暂时不可用，可以稍后重试或放宽条件。",
  "items": [],
  "state": {
    "intent": "recommend",
    "action": "recommend",
    "result_status": "tool_error",
    "tool_error": "recommendation_failed"
  }
}
```

Agent 会保留上一轮成功推荐商品，所以无结果或工具错误之后，用户仍可以追问“为什么第一款适合我”来解释上一轮成功结果。

## Chat Stream

`POST /chat/stream` 复用 `/chat` 请求体，用 SSE 返回事件。

正常事件顺序：

```text
start -> delta -> items -> state -> done
```

可恢复的推荐工具错误仍使用正常事件顺序，并在 `state` 事件中包含 `result_status="tool_error"` 和 `tool_error="recommendation_failed"`；这类错误不会发送 `event: error`。

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
