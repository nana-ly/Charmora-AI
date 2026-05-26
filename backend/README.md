# ShopGuide RAG 后端

本目录是 ShopGuide RAG 的 FastAPI 后端，提供商品推荐和多轮导购接口。当前后端默认使用 RAG 向量检索召回商品；如果向量检索不可用，推荐链路会自动回退到本地关键词检索。开启 LLM 配置后，会尝试用 OpenAI 兼容接口生成更自然的推荐理由。

更多实现细节见：[后端技术文档](../docs/后端技术文档.md)
接口字段契约见：[API 接口契约](../docs/api.md)

---

## 当前能力

- `GET /`：服务基本信息。
- `GET /health`：健康检查。
- `POST /rag/search`：RAG 向量检索调试接口。
- `POST /recommend`：单轮商品推荐，默认使用 RAG 向量检索，`RETRIEVER_MODE=keyword` 时切回关键词检索。
- `POST /chat`：多轮导购对话，默认使用规则版 `SimpleAgentRunner`；`AGENT_RUNNER=langgraph` 时切换到 LangGraph 首版 Runner，响应字段保持兼容。
- `POST /chat/stream`：多轮导购第一版事件级 SSE 流式接口。

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

FastAPI 自动接口文档：

```text
http://127.0.0.1:8000/docs
```

如果 `8000` 端口被占用，可以改用 `8001` 等空闲端口。

---

## 环境变量

可复制 `.env.example` 作为本地配置参考：

```text
AGENT_RUNNER=simple
RETRIEVER_MODE=vector
DEFAULT_TOP_K=3

# RAG 向量检索配置
embedding_url=https://dashscope.aliyuncs.com/compatible-mode/v1
embedding_api=
embedding_model=text-embedding-v4
embedding_dimensions=1024

LLM_ENABLED=false
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=8
```

默认配置不依赖外部大模型服务。只有 `LLM_ENABLED=true` 且 `LLM_API_KEY` 非空时，后端才会尝试调用 LLM；调用失败会自动回退到模板理由，不影响接口返回。

`AGENT_RUNNER=simple` 使用当前规则版编排器，适合本地稳定闭环；`AGENT_RUNNER=langgraph` 启用 LangGraph 首版编排器。Runner 切换只影响后端内部 `/chat` 编排方式，不改变 `/chat`、`/chat/stream` 请求体、响应字段和商品卡片字段。

`RETRIEVER_MODE=vector` 时，`/recommend` 会复用 `rag/.chroma/products` 的 ChromaDB 商品向量索引，并通过 `embedding_url`、`embedding_api`、`embedding_model`、`embedding_dimensions` 调用兼容 OpenAI Embeddings API 的服务生成查询向量。`RETRIEVER_MODE=keyword` 时，推荐链路使用本地关键词检索，可离线运行。

---

## 快速验收

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

单轮推荐：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/recommend" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"query":"预算9000以内，想买拍照和剪视频好的手机"}'
```

RAG 检索调试：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/rag/search" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"query":"适合熬夜后修护的抗初老精华","top_k":5}'
```

多轮导购：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"session_id":"demo-session","message":"预算9000以内的拍照手机"}'
```

多轮导购 SSE：

```powershell
curl.exe -N `
  -H "Accept: text/event-stream" `
  -H "Content-Type: application/json; charset=utf-8" `
  -X POST "http://127.0.0.1:8000/chat/stream" `
  -d '{"session_id":"demo-session","message":"预算9000以内的拍照手机"}'
```

验收重点：

- `/health` 返回 `{"status":"ok"}`。
- `/rag/search` 返回 `query`、`items`，用于检查向量召回结果和 evidence。
- `/recommend` 返回 `query`、`filters`、`items`。
- `/chat` 返回 `session_id`、`reply`、`items`、`state`；`AGENT_RUNNER=simple` 和 `AGENT_RUNNER=langgraph` 下字段保持一致。
- `/chat/stream` 返回 `text/event-stream`，正常事件顺序为 `start -> delta -> items -> state -> done`，业务异常事件顺序为 `start -> error -> done`。
- `items` 中的商品卡片稳定包含 `product_id`、`title`、`brand`、`price`、`reason`、`evidence`。

---

## 目录结构

```text
backend/
  main.py                  FastAPI 应用入口和路由
  recommendation.py        兼容入口，继续导出推荐链路函数
  core/                    应用配置和错误类型
  schemas/                 推荐、商品、对话接口模型
  recommendation_core/     推荐核心链路
  retrieval/               检索抽象、关键词检索、RAG 向量检索适配器
  llm/                     可选 LLM 理由生成
  agent/                   多轮 Agent、Runner 工厂和 LangGraph 首版编排器
  tests/                   后端测试
```

---

## 测试与检查

在仓库根目录运行后端测试：

```powershell
python -m pytest backend/tests -q
```

在 `backend` 目录运行 Ruff：

```powershell
cd backend
uv run ruff check .
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
预算9000以内的拍照手机
再便宜一点
为什么推荐第一款
```
