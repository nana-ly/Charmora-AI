# ShopGuide RAG 后端

本目录是 ShopGuide RAG 的 FastAPI 后端，提供商品推荐和多轮导购接口。当前后端默认使用本地商品 JSON 数据集和关键词检索，可以离线跑通最小闭环；如果开启 LLM 配置，会尝试用 OpenAI 兼容接口生成更自然的推荐理由。

更多实现细节见：[后端技术文档](../docs/后端技术文档.md)
接口字段契约见：[API 接口契约](../docs/api.md)

---

## 当前能力

- `GET /`：服务基本信息。
- `GET /health`：健康检查。
- `POST /recommend`：单轮商品推荐。
- `POST /chat`：多轮导购对话，支持推荐、偏好调整、推荐解释和信息追问。

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
RETRIEVER_MODE=keyword
DEFAULT_TOP_K=3

LLM_ENABLED=false
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=8
```

默认配置不依赖外部大模型服务。只有 `LLM_ENABLED=true` 且 `LLM_API_KEY` 非空时，后端才会尝试调用 LLM；调用失败会自动回退到模板理由，不影响接口返回。

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

多轮导购：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"session_id":"demo-session","message":"预算9000以内的拍照手机"}'
```

验收重点：

- `/health` 返回 `{"status":"ok"}`。
- `/recommend` 返回 `query`、`filters`、`items`。
- `/chat` 返回 `session_id`、`reply`、`items`、`state`。
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
  retrieval/               检索抽象、关键词检索、向量检索占位
  llm/                     可选 LLM 理由生成
  agent/                   轻量多轮 Agent
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
