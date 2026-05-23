# ShopGuide RAG API 接口契约

本文档用于固定 ShopGuide RAG 的接口边界、字段契约和模块依赖关系。后续可以在内部替换商品数据来源或检索实现，但不要随意修改 Android 已依赖的字段名。

## 本地开发地址

```text
http://127.0.0.1:8000
```

---

## 模块边界

### Android 客户端

Android 客户端负责页面展示和用户交互，不负责后端推荐逻辑。

```text
输入：
用户在 Android 页面输入一句自然语言需求

调用：
POST /recommend

读取：
items[].product_id
items[].title
items[].brand
items[].price
items[].reason
items[].evidence
```

### 推荐后端

推荐后端负责把 Android 请求、条件解析、商品候选集、RAG 检索和推荐理由串成稳定接口。

```text
输入：
Android 客户端传入的 query

处理：
1. 解析 query，得到 filters
2. 基于 filters 筛选候选商品
3. 调用商品数据与检索模块的 retrieve 函数
4. 组装 Android 商品卡片字段

输出：
稳定的 /recommend 响应 JSON
```

### 商品数据与 RAG 检索模块

商品数据与 RAG 检索模块负责提供商品列表和检索能力，不负责 Android 字段组装。

```python
# 提供给推荐后端的商品列表。
# 每个商品至少需要包含 product_id、title、brand、price 或 base_price。
products: list[dict]


def retrieve(
    query: str,
    candidates: list[dict] | None = None,
    top_k: int = 3,
) -> list[dict]:
    """根据用户需求和候选商品，返回 Top K 检索结果。

    返回结果建议包含 product 和 evidence：
    - product：原始商品字典
    - evidence：用于解释匹配原因的中文依据
    """
```

---

## Health

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

---

## Root

```http
GET /
```

Response:

```json
{
  "name": "ShopGuide RAG API",
  "status": "running"
}
```

---

## Recommend

### 接口定位

`POST /recommend` 是给 Android 使用的核心推荐接口。当前已经组装真实推荐链路，并保留空结果和异常兜底；后续替换真实 RAG 检索时不改变 Android 依赖字段。

### 请求

```http
POST /recommend
Content-Type: application/json
```

```json
{
  "query": "预算9000以内，想买拍照和剪视频好的手机"
}
```

### 请求字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | `string` | 是 | 用户输入的自然语言购物需求，例如预算、品类、使用场景、偏好。 |

### 响应

```json
{
  "query": "预算9000以内，想买拍照和剪视频好的手机",
  "filters": {
    "category": "数码电子",
    "max_price": 9000,
    "brand": null,
    "keywords": ["拍照", "剪视频", "手机"]
  },
  "items": [
    {
      "product_id": "p_digital_001",
      "title": "Apple iPhone 17 Pro",
      "brand": "Apple",
      "price": 8999,
      "reason": "这款手机适合预算9000以内，并且重视拍照和剪视频体验的用户。",
      "evidence": "匹配关键词：拍照、剪视频；价格符合9000以内预算。"
    }
  ]
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `query` | `string` | 原样返回用户输入，方便 Android 做调试和展示。 |
| `filters.category` | `string \| null` | 后端解析出的商品品类，例如 `数码电子`、`美妆护肤`。 |
| `filters.max_price` | `number \| null` | 后端解析出的最高预算。 |
| `filters.brand` | `string \| null` | 后端解析出的品牌偏好。 |
| `filters.keywords` | `string[]` | 后端从 query 中命中的关键词。 |
| `items` | `array` | 推荐商品列表，目标数量为 3 个。 |
| `items[].product_id` | `string` | 商品唯一 ID。 |
| `items[].title` | `string` | 商品名称。 |
| `items[].brand` | `string` | 商品品牌。 |
| `items[].price` | `number` | 商品价格。 |
| `items[].reason` | `string` | 给用户看的中文推荐理由。 |
| `items[].evidence` | `string` | 给用户看的中文匹配依据。 |
| `error` | `string` | 可选字段。仅当检索模块异常时返回，Android 可以忽略该字段并继续展示兜底商品。 |

### Android 必须依赖的稳定字段

以下字段名固定。后续可以增加字段，但不要改名或删除字段。

```text
items[].product_id
items[].title
items[].brand
items[].price
items[].reason
items[].evidence
```

### 后端内部推荐链路约定

```text
query
  ↓
extract_filters(query)
  ↓
choose_candidates(products, filters)
  ↓
retrieve(query, candidates, top_k=3)
  ↓
build_response_item(query, retrieved_item)
  ↓
return JSON
```

### 兜底策略

```text
1. 完整条件筛选：品类 + 预算 + 品牌
2. 去掉品牌限制
3. 去掉预算限制，只保留品类
4. 全库检索
5. 检索为空或异常时返回 fallback_items
```

兜底商品仍然保持 Android 依赖字段稳定：

```json
{
  "product_id": "fallback_001",
  "title": "通用推荐商品 1",
  "brand": "系统推荐",
  "price": 0,
  "reason": "当前根据「用户需求」返回兜底推荐，真实检索结果暂不可用。",
  "evidence": "后端兜底逻辑触发。"
}
```

### 最终演示问题

```text
预算9000以内，想买拍照和剪视频好的手机
敏感肌能用的抗初老精华
夏天通勤穿的凉快 T 恤
新手想买精品速溶咖啡
```

### 最终验收口径

- `/recommend` 请求字段固定为 `query`
- `/recommend` 响应字段固定为 `query`、`filters`、`items`
- `items` 内核心字段固定为 `product_id`、`title`、`brand`、`price`、`reason`、`evidence`
- Android 可以按这些字段开发商品卡片
- 商品数据与检索模块需要向推荐后端提供 `products` 和 `retrieve`
- 检索为空或异常时，接口仍返回 3 个可展示商品卡片

---

## Planned MVP APIs

```http
POST /api/chat
POST /api/chat/stream
POST /api/images/upload
GET  /api/products/{product_id}
POST /api/knowledge/documents/upload
POST /api/knowledge/index
POST /api/feedback
```
