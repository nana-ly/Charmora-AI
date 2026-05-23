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
└── scripts/                  # 项目辅助脚本
```

## 快速开始

启动后端服务：

```powershell
cd backend
uv sync
uv run fastapi dev main.py
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
- [API 草案](docs/api.md)
- [项目说明](docs/项目说明.md)
- [Android MVP 方案](docs/Android原生3天最小闭环方案.md)
