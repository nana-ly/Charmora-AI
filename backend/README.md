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

## 导购 Agent 架构合同

`/chat` 和 `/chat/stream` 使用可控状态机式导购 Agent。LLM 只负责用户理解和可选理由生成；商品存在性、负反馈排除、筛选、排序和卡片构造由后端确定性逻辑完成。

稳定行为：
- `/chat` 推荐成功时刷新 `last_items`、`last_successful_items`、`last_successful_result_id`、`last_successful_query` 和 `last_successful_filters`。
- 推荐无结果时返回 HTTP 200、`items=[]`、`state.result_status="no_results"` 和 `state.relax_options`，不清空上一轮可解释结果。
- 推荐工具异常时返回 HTTP 200、`items=[]`、`state.result_status="tool_error"` 和 `state.tool_error="recommendation_failed"`；也可按合同检查 `result_status="tool_error"`。该分支不暴露 `relax_options`，不清空 `last_items` 或 `last_successful_items`。
- 解释请求读取 `last_items`；没有序号时默认解释第 1 个商品，数字序号按 1-based 处理。
- 负反馈只作用于当前活跃购买目标。规则解析是兜底路径，不会在 LLM 成功后自动补齐额外负反馈。
- 跨品类切换会归档旧购买上下文；用户疑似回到旧目标时先返回待确认状态，而不是直接恢复。
- `/chat/stream` 对成功、无结果、工具错误、负反馈 noop、待恢复状态均输出 `start -> delta -> items -> state -> done`。只有未被 Agent 转换成稳定 `ChatResponse` 的异常才输出 `start -> error -> done`。

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
CONVERSATION_STORE_MODE=memory
CONVERSATION_STORE_PATH=data/conversations.sqlite3

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

`AGENT_RUNNER=langgraph` 是当前唯一支持的 Agent Runner。`CONVERSATION_STORE_MODE=memory` 使用进程内会话状态；设置为 `sqlite` 时会通过 `CONVERSATION_STORE_PATH` 持久化完整 `ConversationState`，用于本地演示服务重启后恢复同一 `session_id` 的多轮上下文。`DEFAULT_TOP_K` 控制推荐默认返回数量。只有 `LLM_ENABLED=true` 且 `LLM_API_KEY` 非空时，后端才会调用 LLM；LLM 不可用或调用失败时只使用模板理由，不会伪造商品结果。Agent 理解层也会校验 LLM 的结构化 JSON，缺字段会补安全默认值，解析或校验失败时只对明显完整的购买请求做保守兜底。

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

允许保留的可用性处理包括：LLM 推荐理由使用模板理由、Agent 理解层对不可信 LLM 输出做保守兜底、`/chat` 推荐工具异常返回 `tool_error`、`/chat/stream` 在流开始后的未处理异常转换为 SSE `error` 事件。

## Agent 多轮行为

`/chat` 和 `/chat/stream` 使用 LangGraph Runner，LLM 理解是主路径，规则只作为安全护栏：

- 明显完整的购买请求在 LLM 不可用、输出缺字段、JSON 无法解析或校验失败时，会通过保守 fallback 转成 `recommend`。
- 用户切换购物目标时，当前购买上下文会先归档，再清空活跃推荐状态，避免新旧品类偏好混在一起。
- 用户疑似回到旧品类时，后端先询问是否恢复之前需求；确认后恢复归档上下文，拒绝后按新约束推荐。
- 明确负反馈会写入当前购买上下文：`不要第 2 个` 写入 `excluded_product_ids`，`不要苹果` 写入顶层 `excluded_brands`。这些字段随购买上下文归档和恢复，不作为跨品类全局偏好。
- 中文序号、当前商品指代和批量排除也走同一安全路径：`不要第二个` 等价于排除第 2 款，`不要这个` 需要已有解释目标，`这几个都不要` 只排除当前成功推荐结果。
- 负反馈不会拼进推荐 query。Agent 会把 `ConversationState` 转成 `NegativeFilters` 传给推荐工具，推荐链路在检索前和构建商品卡片前各执行一次 product_id/brand 硬过滤。
- `/chat.state` 会额外返回 `excluded_product_ids`、`excluded_brands`、`latest_attempt_status`，本轮识别到负反馈时返回 `negative_feedback`。
- 推荐工具异常会返回稳定 `tool_error` 对话响应：`items=[]`、`state.result_status="tool_error"`、`state.tool_error="recommendation_failed"`。这不会覆盖上一轮成功商品，也不会伪造商品。
- 无结果或工具错误之后，用户仍可追问上一轮成功推荐的解释。

### 泛品类推荐与多轮状态

`/chat` 和 `/chat/stream` 支持“推荐手机”“推荐护肤品”这类泛品类请求。Agent 会写入 `state.preferences.target_category`、`category`、`canonical_target_key` 和本轮 `is_broad_category_request`，并先返回代表性推荐；用户后续补充预算、品牌、用途时会清除 stale broad 标记。

负反馈只作为结构化过滤条件进入状态，例如“推荐手机，不要苹果”会保留 `excluded_brands=["苹果"]`，但 query 不会包含“不要苹果”。“推荐手机，不要第2个，不要苹果”在 MVP 下只应用 item-index 单字段负反馈，query 仍会移除全部负向短语。

目标切换使用 `canonical_target_key` 判断。`手机` 与 `耳机` 都属于 `数码电子`，但会被视为不同购买目标；`护肤` 与 `护肤品` 会归为同一个 `skin_care` 目标。恢复旧目标时，`pending_restore_category` 保存 canonical key，`pending_restore_display_target` 只用于展示文案。

推荐链路的 `extract_filters()` 会把“护肤品”“美妆”“化妆品”统一映射到 catalog category `美妆护肤`，因此理解层、query_builder 和向量检索过滤条件使用同一类目语义。

## Shopping Agent Understanding Fallback

The `/chat` and `/chat/stream` contracts stay unchanged. The backend understanding flow is:

1. Ask the LLM for one JSON object.
2. Normalize safe schema issues before Pydantic validation, including `target_item_index <= 0` to `None` and non-object `preference_updates` to `{}`.
3. If the LLM output is invalid, empty for an active context, or asks for clarification while a purchase context exists, use deterministic fallback rules.
4. Short price feedback such as `太贵了` or `便宜点` with an active purchase context becomes `price_direction=lower` and `avoid_current_price_band=True`.
5. If the backend still cannot infer the update, it uses context-aware clarification instead of asking for a new category.

Local verification:

```powershell
cd backend
uv run pytest tests/test_agent.py -v
uv run ruff check .
```

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
    sqlite_memory.py       SQLiteConversationStore，会话状态持久化实现
  tests/                   后端测试
```

## 测试与检查

在后端目录运行：

```powershell
cd backend
uv run pytest tests -q
uv run ruff check .
```

Agent resilience 相关的确定性测试不需要真实 LLM 凭证。常用定向命令：

```powershell
cd backend
uv run pytest tests/test_agent.py tests/test_main.py -q
uv run pytest tests/test_main.py::test_chat_tool_error_keeps_response_shape tests/test_main.py::test_chat_stream_tool_error_returns_success_events -q
```
