## ChromaDB 商品检索脚本

`rag/` 目录只负责商品向量索引和相似检索，不和 `backend/` 的服务依赖混在一起。

### 安装依赖

```bash
uv sync
```

如果不使用 `uv`，也可以按 `pyproject.toml` 安装 `chromadb`、`openai`、`python-dotenv` 和测试依赖。

### 配置百炼 Embedding

在仓库根目录 `.env` 或当前 shell 里配置：

```bash
export embedding_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
export embedding_api="your-api-key"
export embedding_model="text-embedding-v4"
export dimention="1024"
```

独立 `rag` 包当前从环境变量读取 `dimention`；CLI 参数使用标准拼写 `--embedding-dimensions`，推荐在命令中显式传入。后端配置读取时兼容 `embedding_dimensions`、`dimention` 和 `dimentions`。

### 建立索引

```bash
uv run python -m shopguide_rag.cli index
```

在 `rag/` 目录执行时，默认索引目录是 `.chroma/products/`，默认数据集目录是 `../ecommerce_agent_dataset/`。后端向量检索默认读取仓库下的 `rag/.chroma/products/`。

如需显式指定维度：

```bash
uv run python -m shopguide_rag.cli --embedding-dimensions 1024 index
```

### 文本检索

```bash
uv run python -m shopguide_rag.cli query --query "适合熬夜后修护的抗初老精华" --top-k 5
```

### 按商品找相似商品

```bash
uv run python -m shopguide_rag.cli query --product-id p_beauty_001 --top-k 5
```

### 当前 collection 设计

- 一个商品一条向量记录。
- embedding 文本包含：标题、品牌、类目、子类目、价格区间、SKU 摘要、营销描述、FAQ 摘要。
- metadata 包含：`product_id`、`title`、`brand`、`category`、`sub_category`、`category_path`、`base_price`、`price_min`、`price_max`、`sku_count`、`faq_count`、`review_count`、`avg_rating`、`has_faq`、`has_reviews`、`sku_keys`，以及常见 SKU 选项字段。
- 默认 embedding 模型是 `text-embedding-v4`，通过百炼兼容 `/v1/embeddings` API 批量生成向量。
