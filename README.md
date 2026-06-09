# ShopGuide RAG

基于 RAG 的多模态电商智能导购 AI Agent。

## 项目结构

```text
ShopGuide-RAG/
├── android/                  # Android 原生客户端
├── backend/                  # FastAPI 后端服务
├── docs/                     # 项目文档、API 文档和部署/启动指南
├── ecommerce_agent_dataset/  # 商品数据集
├── eval/                     # 评测数据集和评测脚本
├── rag/                      # 独立商品向量索引与 ChromaDB 检索脚本
└── scripts/                  # 项目辅助脚本
```

## 快速开始

启动后端服务：

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
