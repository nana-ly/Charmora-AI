# ShopGuide RAG API 接口契约

本文档用于固定 ShopGuide RAG 的接口边界、字段契约和模块依赖关系。后续可以替换商品数据来源、检索实现或 Agent 编排方式，但不要随意修改客户端已依赖的字段名。

## 本地开发地址

```text
http://127.0.0.1:8000
```

---

## 模块边界

### 客户端

客户端负责页面展示和用户交互，不负责后端推荐逻辑。

```text
核心调用：
POST /recommend
POST /chat

稳定读取：
items[].product_id
items[].title
items[].brand
items[].price
items[].reason
items[].evidence
```

### 推荐后端

推荐后端负责把请求、条件解析、商品候选集、检索结果和推荐理由串成稳定接口。

```text
输入：
自然语言购物需求

处理：
1. 解析 query 或 message，得到 filters 和对话状态
2. 基于 filters 筛选候选商品
3. 调用 retrieval 检索层
4. 可选调用 LLM 理由服务
5. 组装商品卡片字段

输出：
稳定的 JSON 响应
```

### 检索与商品数据模块

检索与商品数据模块负责提供商品列表和召回能力，不负责客户端字段组装。

```python
def search(
    query: str,
    candidates: list[dict] | None = None,
    top_k: int = 3,
) -> list[RetrievalResult]:
    """根据用户需求和候选商品，返回 Top K 检索结果。"""
```

`RetrievalResult` 至少应包含：

```text
product：原始商品字典
evidence：用于解释匹配原因的中文依据
score：检索或排序分数
```

---

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

---

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

---

## Recommend

### 接口定位

`POST /recommend` 是核心推荐接口。当前已经组装真实推荐链路，并保留空结果和异常兜底；后续替换真实 RAG 检索时不改变客户端依赖字段。

### 请求

```http
POST /recommend
Content-Type: application/json
```

```json
{
  "query": "预算9000以内，想买拍照和剪视频好的手机"
}
```

### 请求字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | `string` | 是 | 用户输入的自然语言购物需求，例如预算、品类、使用场景、偏好。 |

### 响应

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
      "reason": "这款手机适合预算9000以内，并且重视拍照和剪视频体验的用户。",
      "evidence": "临时匹配：命中 手机、拍照、剪视频；来自结构化筛选结果。"
    }
  ]
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `query` | `string` | 原样返回用户输入，方便调试和展示。 |
| `filters.category` | `string \| null` | 后端解析出的商品品类，例如 `数码电子`、`美妆护肤`。 |
| `filters.max_price` | `number \| null` | 后端解析出的最高预算。 |
| `filters.brand` | `string \| null` | 后端解析出的品牌偏好。 |
| `filters.keywords` | `string[]` | 后端从 query 中命中的关键词。 |
| `items` | `array` | 推荐商品列表，目标数量为 3 个。 |
| `items[].product_id` | `string` | 商品唯一 ID。 |
| `items[].title` | `string` | 商品名称。 |
| `items[].brand` | `string` | 商品品牌。 |
| `items[].price` | `number` | 商品价格。 |
| `items[].reason` | `string` | 给用户看的中文推荐理由。 |
| `items[].evidence` | `string` | 给用户看的中文匹配依据。 |
| `error` | `string` | 可选字段。仅当推荐链路异常时返回，客户端可以忽略该字段并继续展示兜底商品。 |

---

## Chat

### 接口定位

`POST /chat` 是多轮导购接口。它在 `/recommend` 的基础上增加 `session_id`、会话状态和意图处理，用于支持追问、偏好调整和推荐解释。

Runner 切换属于后端内部实现：`AGENT_RUNNER=simple` 使用规则版 Runner，`AGENT_RUNNER=langgraph` 使用 LangGraph 首版 Runner。两种模式下请求字段、HTTP 状态码、响应字段和商品卡片字段保持一致。

### 请求

```http
POST /chat
Content-Type: application/json
```

```json
{
  "session_id": "demo-session",
  "message": "预算9000以内的拍照手机"
}
```

### 请求字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID，同一个用户连续对话应保持一致。 |
| `message` | `string` | 是 | 用户当前轮输入。 |

### 响应

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
      "reason": "Apple iPhone 17 Pro 与你的需求「预算9000以内的拍照手机」匹配，临时匹配：命中 手机、拍照；来自结构化筛选结果。",
      "evidence": "临时匹配：命中 手机、拍照；来自结构化筛选结果。"
    }
  ],
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

### 响应字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | `string` | 原样返回会话 ID。 |
| `reply` | `string` | 给用户展示的对话回复。 |
| `items` | `array` | 当前轮推荐商品列表；信息不足时可能为空。 |
| `state.intent` | `string` | 当前轮意图，取值见下方说明。 |
| `state.preferences` | `object` | 当前会话中沉淀的偏好摘要。 |

当前支持的 `state.intent`：

```text
recommend
update_preference
explain
clarify
```

### 兼容性约定

```text
AGENT_RUNNER -> simple/langgraph -> ChatResponse
```

- 客户端不需要感知 Runner 类型。
- LangGraph 首版不新增客户端必填字段，也不改变 `state.intent` 取值。
- `/chat` 通过现有 `RecommendationTool` 调用推荐入口；RAG、关键词检索和 fallback 仍由推荐链路负责。
- 商品卡片继续稳定包含 `product_id`、`title`、`brand`、`price`、`reason`、`evidence`。

---

## Chat Stream

### 接口定位

`POST /chat/stream` 是多轮导购的第一版 SSE 流式接口。它复用 `/chat` 的请求体和业务语义，响应采用事件级 SSE，不承诺 token 级文本流式输出。

### 请求

```http
POST /chat/stream
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "session_id": "demo-session",
  "message": "预算9000以内的拍照手机"
}
```

请求字段与 `POST /chat` 相同：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID，同一个用户连续对话应保持一致。 |
| `message` | `string` | 是 | 用户当前轮输入。 |

### 响应

```http
Content-Type: text/event-stream
```

正常事件顺序固定为：

```text
start -> delta -> items -> state -> done
```

异常事件顺序固定为：

```text
start -> error -> done
```

请求体验证失败仍由 FastAPI 返回 `422`，不会进入 SSE 流。进入流式处理后的业务异常通过 `event: error` 返回，并随后发送 `event: done`。

### 事件说明

| 事件 | 说明 |
| --- | --- |
| `start` | 流式响应开始，通常包含 `session_id`。 |
| `delta` | 事件级回复片段，用于逐步展示导购回复；第一版不承诺 token 级粒度。 |
| `items` | 当前轮推荐商品列表。商品字段保持 `product_id`、`title`、`brand`、`price`、`reason`、`evidence`。 |
| `state` | 当前会话状态，与 `/chat` 的 `state` 语义一致。 |
| `error` | 进入流式处理后的业务异常信息。 |
| `done` | 本次 SSE 响应结束。 |

---

## 稳定字段

以下商品字段名固定。后续可以增加字段，但不要改名或删除字段。

```text
items[].product_id
items[].title
items[].brand
items[].price
items[].reason
items[].evidence
```

---

## 后端内部推荐链路

```text
query
  ↓
extract_filters(query)
  ↓
choose_candidates(products, filters)
  ↓
KeywordRetriever.search(query, candidates, top_k=3)
  ↓
build_response_item(query, retrieved_item)
  ↓
return JSON
```

---

## 后端内部 Agent 链路

```text
session_id + message
  ↓
InMemoryConversationStore
  ↓
AgentPolicy.detect_intent(message)
  ↓
RecommendationTool.run(...)
  ↓
更新 preferences、last_filters、last_items
  ↓
return ChatResponse
```

---

## 兜底策略

推荐候选为空时：

```text
1. 完整条件筛选：品类 + 预算 + 品牌
2. 去掉品牌限制
3. 去掉预算限制，只保留品类
4. 全库检索
5. 检索为空或异常时返回 fallback_items
```

兜底商品仍然保持稳定字段：

```json
{
  "product_id": "fallback_001",
  "title": "通用推荐商品 1",
  "brand": "系统推荐",
  "price": 0,
  "reason": "当前根据「用户需求」返回兜底推荐，真实检索结果暂不可用。",
  "evidence": "后端兜底逻辑触发。"
}
```

---

## 演示问题

单轮推荐：

```text
预算9000以内，想买拍照和剪视频好的手机
敏感肌能用的抗初老精华
夏天通勤穿的凉快 T 恤
新手想买精品速溶咖啡
```

多轮对话：

```text
预算9000以内的拍照手机
再便宜一点
为什么推荐第一款
```

---

## 当前接口清单

```http
GET  /
GET  /health
POST /recommend
POST /chat
POST /chat/stream
```

## 后续可扩展接口

```http
POST /images/upload
GET  /products/{product_id}
POST /knowledge/documents/upload
POST /knowledge/index
POST /feedback
```
