# 绮饰集 Charmora

一个面向饰品与生活方式小物的 AI 选购应用。Android 商城、FastAPI/LangGraph Agent、商品事实库、购物车和模拟订单共同组成“浏览 → 推荐/比较 → 加购 → 结算确认 → 订单查询”的可控商务闭环。

AI 不是独立聊天演示，也不会替用户静默下单：它读取数据库中的真实商品、价格与库存，结算前生成预览，只有得到明确确认才创建订单。

## 项目结构

```text
Charmora-AI/
├── android/                  # Android 原生客户端
├── backend/                  # FastAPI 后端服务
├── docs/                     # 项目文档、API 文档和部署/启动指南
├── ecommerce_agent_dataset/  # 商品数据集
├── eval/                     # 评测数据集和评测脚本
├── rag/                      # 独立商品向量索引与 ChromaDB 检索脚本
└── scripts/                  # 项目辅助脚本
```

## 快速开始

启动后端服务。未配置 PostgreSQL 时，服务会自动创建本地 SQLite 演示库并导入 42 个模拟商品：

```powershell
cd backend
uv sync
Copy-Item .env.example .env
uv run fastapi dev main.py
```

后端默认 `RETRIEVER_MODE=vector`。如果本地没有 Chroma 索引或 `embedding_api`，可在 `backend/.env` 中临时设置：

```env
RETRIEVER_MODE=keyword
```

打开 API 文档：

```text
http://127.0.0.1:8000/docs
```

Android 模拟器默认访问 `http://10.0.2.2:8000/`。安装到真机后，在商城右上角设置中填写运行后端电脑的局域网地址，例如 `http://192.168.1.10:8000/`；应用会显示连接检测结果。

视觉原型位于 [`docs/ui-prototype/index.html`](docs/ui-prototype/index.html)，采用灰调玫瑰粉、雾紫和暖白的统一设计系统。

运行检查：

```powershell
cd backend
uv run pytest
uv run ruff check .
```

## 文档

- [环境配置指南](docs/setup.md)
- [API 接口契约](docs/api.md)
- [项目说明](docs/项目说明.md)
- [后端技术文档](docs/后端技术文档.md)
- [后端 README](backend/README.md)
- [RAG 索引脚本说明](rag/README.md)
- [评测工具说明](eval/README.md)
- [Android MVP 方案](docs/Android原生3天最小闭环方案.md)
