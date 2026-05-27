# ShopGuide RAG 后端

本目录是 ShopGuide RAG 的 FastAPI 后端，提供商品推荐、RAG 调试检索和多轮导购接口。当前后端默认使用 RAG 向量检索；当 `RETRIEVER_MODE=vector` 时，向量检索初始化或查询失败会向上暴露错误，不会静默切换到关键词检索。需要离线关键词检索时，请显式设置 `RETRIEVER_MODE=keyword`。

更多实现细节见：[后端技术文档](../docs/后端技术文档.md)  
接口字段契约见：[API 接口契约](../docs/api.md)

## 当前能力

- `GET /`：服务基本信息。
- `GET /health`：健康检查。
- `POST /rag/search`：RAG 向量检索调试接口。
- `POST /recommend`：单轮商品推荐。
- `POST /chat`：多轮导购对话，使用 LangGraph Runner 维护会话状态并调用推荐工具。
- `POST /chat/stream`：多轮导购 SSE 事件流接口。

## 快速运行

```powershell
cd backend
uv sync
uv run fastapi dev main.py --host 127.0.0.1 --port 8000
```

本地服务地址：

```text
http://127.0.0.1:8000
```

FastAPI 文档：

```text
http://127.0.0.1:8000/docs
```

## 环境变量

可复制 `.env.example` 作为本地配置参考：

```text
AGENT_RUNNER=langgraph
RETRIEVER_MODE=vector
DEFAULT_TOP_K=3
LOG_LEVEL=INFO

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

`AGENT_RUNNER=langgraph` 是当前唯一支持的 Agent Runner。`DEFAULT_TOP_K` 控制推荐默认返回数量。只有 `LLM_ENABLED=true` 且 `LLM_API_KEY` 非空时，后端才会调用 LLM；LLM 不可用或调用失败时只使用模板理由，不会伪造商品结果。

## 日志级别

后端使用标准库 `logging` 输出到控制台，通过 `LOG_LEVEL` 调整详细程度：

- `DEBUG`：输出调试信息，例如查询长度、消息长度、检索模式和数量。
- `INFO`：默认级别，输出关键请求和流程信息。
- `WARNING`：只输出警告和错误。
- `ERROR`：只输出错误。

日志不会记录 API Key、完整用户消息、完整用户 query、完整对话历史或外部服务完整响应。

本地调试时可临时开启 DEBUG：

```powershell
$env:LOG_LEVEL="DEBUG"
uv run fastapi dev main.py --host 127.0.0.1 --port 8000
```

## 推荐行为

推荐链路不再返回预置商品：

- `choose_candidates()` 只按结构化条件筛选，不自动忽略品类、预算或品牌约束。
- 检索结果为空时，`items` 返回空数组。
- 推荐链路异常时，异常向上抛出，由测试或 API 层暴露错误。
- `RETRIEVER_MODE=vector` 只使用向量检索；`RETRIEVER_MODE=keyword` 才使用关键词检索。

允许保留的可用性处理包括：LLM 推荐理由使用模板理由、LLM 意图解析使用当前用户文本、`/chat/stream` 在流开始后的异常转换为 SSE `error` 事件。

## 后端链路

当前后端分层链路为：

```text
api/* -> services/* -> retrieval/* + recommendation_core/* -> schemas/*
```

`/recommend` 的推荐调用链路为：

```text
api.recommend
  -> services.recommendation_service.run_recommendation
  -> services.retriever_factory.select_retriever
  -> recommendation_core.pipeline.recommend_products
  -> Retriever.search
  -> recommendation_core.response_builder.build_response_item
```

## 目录结构

```text
backend/
  main.py                  FastAPI 应用入口，只创建 app 并挂载路由
  api/                     HTTP 路由：health、recommend、rag、chat
  services/                应用服务装配：推荐入口和检索器选择
  core/                    应用配置和控制台日志配置
  schemas/                 推荐、商品、对话接口模型
  recommendation_core/     推荐核心链路
  retrieval/               检索抽象、关键词检索、RAG 向量检索适配器
  llm/                     LLM 客户端、Agent 意图解析适配、推荐理由生成
  agent/                   多轮 Agent、Runner 工厂和 LangGraph 编排器
  tests/                   后端测试
```

## 测试与检查

在仓库根目录运行：

```powershell
python -m pytest backend/tests -q
python -m ruff check backend
```
