# ShopGuide RAG 后端说明

本文档说明 ShopGuide RAG 后端的运行方式、接口契约、推荐链路、兜底策略和联调约定。后端当前提供稳定的 `/recommend` 推荐接口，负责把用户自然语言需求转换为可供 Android 展示的商品卡片数据。

---

## 快速运行

进入后端目录：

```powershell
cd backend
```

启动开发服务：

```powershell
uv run fastapi dev main.py --host 127.0.0.1 --port 8000
```

如果当前环境没有 `uv`，可以使用：

```powershell
python -m fastapi dev main.py --host 127.0.0.1 --port 8000
```

本地服务地址：

```text
http://127.0.0.1:8000
```

接口文档页面：

```text
http://127.0.0.1:8000/docs
```

---

## 快速验收

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

预期返回：

```json
{
  "status": "ok"
}
```

推荐接口自测：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/recommend" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"query":"预算9000以内，想买拍照和剪视频好的手机"}'
```

验收重点：

```text
1. /health 返回 {"status": "ok"}
2. /recommend 返回 HTTP 200
3. items 尽量返回 3 个商品
4. 每个商品都有 product_id、title、brand、price、reason、evidence
5. 检索失败或无数据时，仍返回 fallback_items，避免 Android 页面空白
```

说明：部分 Windows PowerShell 终端可能把中文显示成乱码，这是终端显示编码问题；接口实际按 UTF-8 处理请求和响应。

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

核心推荐接口。Android 传入一句自然语言购物需求，后端返回商品卡片列表。

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
      "reason": "Apple iPhone 17 Pro 与你的需求「预算9000以内，想买拍照和剪视频好的手机」匹配，匹配关键词：拍照、剪视频；价格符合预算。",
      "evidence": "匹配关键词：拍照、剪视频；价格符合预算。"
    }
  ]
}
```

异常兜底时可能额外返回 `error` 字段。该字段用于后端调试，Android 可以忽略。

---

## Android 字段约定

Android 商品卡片只需要稳定读取 `items` 内字段：

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
error
```

后端可以继续增加字段，但不要修改或删除 Android 已依赖的 `items` 字段名。

---

## 推荐链路

`/recommend` 当前直接调用 `recommend_products(query)` 编排推荐流程：

```text
request.query
  -> recommend_products(query)
     -> extract_filters(query)
     -> choose_candidates(products, filters)
     -> retrieve(query, candidates, top_k=3)
     -> build_response_item(query, retrieved_item)
     -> 如果结果为空或异常，返回 fallback_items(query)
  -> 返回 query、filters、items，可选 error
```

核心职责：

```text
1. 解析用户需求，得到品类、预算、品牌和关键词
2. 从本地商品数据中筛选候选商品
3. 对候选商品做临时检索和排序
4. 生成中文推荐理由和匹配依据
5. 组装 Android 可直接展示的商品卡片字段
6. 在空结果或异常场景下返回稳定兜底商品
```

---

## 需求解析能力

`extract_filters(query)` 会从自然语言需求中解析：

```text
category：品类
max_price：最高预算
brand：品牌偏好
keywords：命中的关键词
```

已支持的品类关键词：

```text
数码电子：手机、耳机、电脑、拍照、剪视频、平板、笔记本、续航、游戏、办公、学生、降噪
美妆护肤：精华、敏感肌、护肤、抗初老、面霜、防晒、保湿、修护、美白、油皮、干皮
服饰运动：T恤、通勤、运动、凉快、速干、外套、夏天、跑步、健身、防晒衣
食品生活：咖啡、速溶、饮品、新手、拿铁、冷萃、低糖、早餐、办公室、精品
```

已支持的预算表达：

```text
9000以内
9000以下
不超过9000
9000左右
预算9000
```

---

## 商品数据与检索

本地商品数据由 `load_products()` 加载：

```text
ecommerce_agent_dataset/*/data/*.json
```

每个商品至少需要包含：

```text
product_id
title
brand
price 或 base_price
category
```

当前检索函数：

```python
def retrieve(
    query: str,
    candidates: list[dict] | None = None,
    top_k: int = 3,
) -> list[dict]:
    """根据用户需求和候选商品返回 Top K 检索结果。"""
```

推荐的检索结果结构：

```python
{
    "product": {
        "product_id": "p_digital_001",
        "title": "Apple iPhone 17 Pro",
        "brand": "Apple",
        "price": 8999,
    },
    "evidence": "匹配关键词：拍照、剪视频；价格符合预算。",
}
```

商品数据与检索模块后续可以替换 `products` 的来源或 `retrieve` 的内部检索逻辑，但需要保持 `/recommend` 请求字段和 Android 已依赖的 `items` 字段不变。

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
2. retrieve 返回空结果
3. retrieve 或外部检索模块抛出异常
```

兜底商品仍然包含 Android 需要的稳定字段：

```text
product_id
title
brand
price
reason
evidence
```

兜底响应示例：

```json
{
  "query": "找一个不存在的商品",
  "filters": {
    "category": null,
    "max_price": null,
    "brand": null,
    "keywords": []
  },
  "items": [
    {
      "product_id": "fallback_001",
      "title": "通用推荐商品 1",
      "brand": "系统推荐",
      "price": 0,
      "reason": "当前根据「找一个不存在的商品」返回兜底推荐，真实检索结果暂不可用。",
      "evidence": "后端兜底逻辑触发。"
    }
  ]
}
```

---

## 文件职责

```text
backend/main.py
  FastAPI 应用入口
  定义 /、/health、/recommend
  接收请求并返回 JSON

backend/recommendation.py
  加载本地商品数据
  解析用户需求
  筛选候选商品
  临时检索和排序
  生成推荐理由
  组装 Android 商品卡片字段
  处理空结果和异常兜底

backend/tests/test_main.py
  测试 FastAPI 接口行为

backend/tests/test_recommendation.py
  测试推荐逻辑函数
```

---

## 主要函数

```python
def load_products(dataset_dir: Path = DATASET_DIR) -> list[dict]:
    """从本地数据集加载商品 JSON，作为推荐商品来源。"""
```

```python
def extract_filters(query: str) -> dict:
    """从用户自然语言需求中解析基础筛选条件。"""
```

```python
def structured_filter(products: list[dict], filters: dict) -> list[dict]:
    """根据品类、预算和品牌对商品列表做第一轮结构化筛选。"""
```

```python
def choose_candidates(products: list[dict], filters: dict) -> list[dict]:
    """选择候选商品；无结果时逐步放宽限制。"""
```

```python
def retrieve(query: str, candidates: list[dict] | None = None, top_k: int = 3) -> list[dict]:
    """临时检索函数：按关键词命中数排序，返回带 evidence 的 Top K 商品。"""
```

```python
def build_response_item(query: str, retrieved_item: dict) -> dict:
    """把检索结果转换成 Android 商品卡片需要的稳定字段。"""
```

```python
def fallback_items(query: str) -> list[dict]:
    """返回固定 3 张兜底商品卡片，避免 Android 页面因为空结果而无法展示。"""
```

```python
def recommend_products(query: str, product_source: list[dict] | None = None, top_k: int = 3) -> dict:
    """组装完整推荐链路，并在检索为空或异常时返回稳定兜底结果。"""
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
/recommend 返回 3 个真实链路商品卡片
extract_filters
get_product_price
structured_filter
choose_candidates
build_response_item
load_products
retrieve
recommend_products
fallback_items
```

---

## 演示问题

最终演示可以直接使用以下问题：

```text
预算9000以内，想买拍照和剪视频好的手机
敏感肌能用的抗初老精华
夏天通勤穿的凉快 T 恤
新手想买精品速溶咖啡
```

每条问题都应返回：

```text
HTTP 200
items 数量尽量为 3
商品包含名称、品牌、价格、推荐理由和匹配依据
```
