# ShopGuide RAG 后端说明

本文档说明 ShopGuide RAG 后端的运行方式、接口契约、模块职责和联调约定。后端当前提供稳定的 `/recommend` 推荐接口和 `/chat` 多轮导购接口；内部已拆分为推荐核心、检索层、可选 LLM 理由层和轻量 Agent 编排层。

---

## 快速运行

进入后端目录并安装依赖：

```powershell
cd backend
uv sync
```

启动开发服务：

```powershell
uv run fastapi dev main.py --host 127.0.0.1 --port 8000
```

本地服务地址：

```text
http://127.0.0.1:8000
```

接口文档页面：

```text
http://127.0.0.1:8000/docs
```

说明：文档示例统一使用 `8000` 端口；如果本机端口冲突，可改用 `8001` 等空闲端口。

---

## 环境变量

可参考 `.env.example`：

```text
RETRIEVER_MODE=keyword
DEFAULT_TOP_K=3
LLM_ENABLED=false
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=8
```

默认配置不依赖外部大模型服务，保证本地最小闭环可以离线运行。只有 `LLM_ENABLED=true` 且 `LLM_API_KEY` 非空时，后端才会尝试调用 OpenAI 兼容接口生成推荐理由；调用失败会自动回退到模板理由，不影响 `/recommend` 和 `/chat` 返回。

---

## 快速验收

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

推荐接口：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/recommend" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"query":"预算9000以内，想买拍照和剪视频好的手机"}'
```

多轮对话接口：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"session_id":"demo-session","message":"预算9000以内的拍照手机"}'
```

验收重点：

```text
1. /health 返回 {"status": "ok"}
2. /recommend 返回 query、filters、items
3. /chat 返回 session_id、reply、items、state
4. items 尽量返回 3 个商品
5. 每个商品都有 product_id、title、brand、price、reason、evidence
6. 检索失败、无数据或 LLM 失败时，接口仍返回稳定兜底结果
```

---

## 接口说明

### `GET /`

用于确认后端应用已经启动。

Response:

```json
{
  "name": "ShopGuide RAG API",
  "status": "running"
}
```

### `GET /health`

用于健康检查。

Response:

```json
{
  "status": "ok"
}
```

### `POST /recommend`

核心推荐接口。客户端传入一句自然语言购物需求，后端返回商品卡片列表。

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
      "price": 8999.0,
      "reason": "Apple iPhone 17 Pro 与你的需求「预算9000以内，想买拍照和剪视频好的手机」匹配，临时匹配：命中 手机、拍照、剪视频；来自结构化筛选结果。",
      "evidence": "临时匹配：命中 手机、拍照、剪视频；来自结构化筛选结果。"
    }
  ]
}
```

异常兜底时可能额外返回 `error` 字段。该字段用于后端调试，客户端可以忽略。

### `POST /chat`

多轮导购接口。客户端传入会话 ID 和用户消息，后端通过轻量 Agent 维护上下文、识别意图并调用推荐工具。

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
      "price": 8999.0,
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

当前支持的对话意图：

```text
recommend：明确推荐需求
update_preference：基于上一轮调整偏好，例如“再便宜一点”
explain：解释上一轮推荐，例如“为什么推荐第一款”
clarify：信息不足时追问预算、品类和偏好
```

---

## 稳定字段约定

商品卡片只需要稳定读取 `items` 内字段：

```text
items[].product_id
items[].title
items[].brand
items[].price
items[].reason
items[].evidence
```

可选调试字段：

```text
query
filters
state
error
```

后端可以继续增加字段，但不要修改或删除客户端已依赖的 `items` 字段名。

---

## 后端架构

```text
backend/main.py
  FastAPI 应用入口，提供 /、/health、/recommend、/chat

backend/core/
  应用配置和统一错误类型

backend/schemas/
  推荐、商品和对话接口的数据结构

backend/recommendation.py
  兼容入口，继续导出旧的推荐函数名

backend/recommendation_core/
  推荐核心链路：需求解析、候选筛选、响应组装、兜底策略

backend/retrieval/
  检索抽象层：Retriever 接口、关键词检索、向量检索占位适配器

backend/llm/
  可选 LLM 接入层：OpenAI 兼容客户端和推荐理由服务

backend/agent/
  轻量多轮 Agent：会话状态、意图策略、工具封装和编排器

backend/tests/
  接口、推荐核心、检索层、LLM 理由层和 Agent 测试
```

整体依赖方向：

```text
FastAPI 路由
  -> schemas
  -> agent / recommendation_core
  -> retrieval / llm
  -> 本地商品数据或后续外部服务
```

---

## 推荐链路

`/recommend` 当前调用 `recommend_products(query)` 编排推荐流程：

```text
request.query
  -> extract_filters(query)
  -> choose_candidates(products, filters)
  -> KeywordRetriever.search(query, candidates, top_k=3)
  -> build_response_item(query, retrieved_item)
  -> 可选 LLMReasonService 生成 reason
  -> 如果结果为空或异常，返回 fallback_items(query)
```

核心职责：

```text
1. 解析用户需求，得到品类、预算、品牌和关键词
2. 从本地商品数据中筛选候选商品
3. 通过检索层对候选商品排序和生成 evidence
4. 生成中文推荐理由
5. 组装客户端可直接展示的商品卡片字段
6. 在空结果或异常场景下返回稳定兜底商品
```

---

## Agent 链路

`/chat` 当前使用 `SimpleAgentRunner`：

```text
session_id + message
  -> InMemoryConversationStore 读取会话状态
  -> AgentPolicy 判断意图
  -> RecommendationTool 调用推荐链路
  -> 更新 preferences、last_filters、last_items
  -> 返回 reply、items、state
```

当前状态存储为内存实现，适合本地开发和演示。后续生产化时可以用同样接口替换为 Redis、数据库或持久化会话服务。

---

## 检索与向量库接入

当前默认检索器是 `KeywordRetriever`，按关键词命中数排序，并返回 `RetrievalResult`：

```python
RetrievalResult(
    product={...},
    evidence="临时匹配：命中 手机、拍照；来自结构化筛选结果。",
    score=2.0,
)
```

向量数据库接入时建议实现 `Retriever.search()`：

```python
def search(
    query: str,
    candidates: list[dict] | None = None,
    top_k: int = 3,
) -> list[RetrievalResult]:
    ...
```

接入原则：

```text
1. 检索层返回 RetrievalResult，不直接拼最终商品卡片
2. evidence 必须是可展示的中文匹配依据
3. 检索失败应抛出明确异常，由推荐链路兜底
4. /recommend 和 /chat 的 items 字段保持不变
```

---

## 兜底策略

候选商品为空时，后端按以下顺序放宽：

```text
1. 使用完整 filters 筛选：品类 + 预算 + 品牌
2. 去掉品牌限制
3. 去掉预算限制
4. 全库检索
5. 仍无可展示结果时返回 fallback_items
```

会触发 `fallback_items(query)` 的场景：

```text
1. 商品源为空
2. 检索层返回空结果
3. 检索层或外部服务抛出异常
4. 可选 LLM 调用失败时，仅 reason 回退，不触发商品兜底
```

---

## 测试和静态检查

在项目根目录运行后端测试：

```powershell
python -m pytest backend/tests -q
```

在 `backend` 目录运行 Ruff：

```powershell
cd backend
uv run ruff check .
```

测试覆盖：

```text
/ 返回服务信息
/health 返回 {"status": "ok"}
/recommend 返回真实链路商品卡片
/chat 返回 Agent 响应和会话状态
core 配置与 LLM 可用性判断
schemas 请求响应模型
recommendation_core 推荐链路
retrieval 检索抽象与关键词检索
llm 可选理由生成与失败回退
agent 多轮状态、意图策略和工具调用
```

---

## 演示问题

```text
预算9000以内，想买拍照和剪视频好的手机
敏感肌能用的抗初老精华
夏天通勤穿的凉快 T 恤
新手想买精品速溶咖啡
```

多轮对话示例：

```text
用户：预算9000以内的拍照手机
用户：再便宜一点
用户：为什么推荐第一款
```
