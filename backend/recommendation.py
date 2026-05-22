"""推荐后端的核心逻辑模块。

本模块从 FastAPI 接口层拆出，负责需求解析、结构化筛选、候选商品兜底、
推荐理由生成和商品卡片字段组装。阶段 3 先提供可单独测试的规则版本，
后续阶段再接入成员 C 的真实商品数据和 RAG 检索函数。
"""

import json
import re
from pathlib import Path
from typing import Any, Callable


DATASET_DIR = Path(__file__).resolve().parent.parent / "ecommerce_agent_dataset"
CATEGORY_RULES = {
    "数码电子": [
        "手机",
        "耳机",
        "电脑",
        "拍照",
        "剪视频",
        "平板",
        "笔记本",
        "续航",
        "游戏",
        "办公",
        "学生",
        "降噪",
    ],
    "美妆护肤": [
        "精华",
        "敏感肌",
        "护肤",
        "抗初老",
        "面霜",
        "防晒",
        "保湿",
        "修护",
        "美白",
        "油皮",
        "干皮",
    ],
    "服饰运动": [
        "T恤",
        "通勤",
        "运动",
        "凉快",
        "速干",
        "外套",
        "夏天",
        "跑步",
        "健身",
        "防晒衣",
    ],
    "食品生活": [
        "咖啡",
        "速溶",
        "饮品",
        "新手",
        "拿铁",
        "冷萃",
        "低糖",
        "早餐",
        "办公室",
        "精品",
    ],
}
EMPTY_FILTERS: dict[str, Any] = {
    "category": None,
    "max_price": None,
    "brand": None,
    "keywords": [],
}


def load_products(dataset_dir: Path = DATASET_DIR) -> list[dict[str, Any]]:
    """从本地数据集加载商品 JSON，作为成员 C 数据未接入前的商品来源。"""
    loaded_products: list[dict[str, Any]] = []

    for product_file in sorted(dataset_dir.glob("*/data/*.json")):
        with product_file.open("r", encoding="utf-8") as file:
            loaded_products.append(json.load(file))

    return loaded_products


products = load_products()


def extract_filters(query: str) -> dict[str, Any]:
    """从用户自然语言需求中解析基础筛选条件。"""
    filters = {
        "category": EMPTY_FILTERS["category"],
        "max_price": EMPTY_FILTERS["max_price"],
        "brand": EMPTY_FILTERS["brand"],
        "keywords": list(EMPTY_FILTERS["keywords"]),
    }

    for category, words in CATEGORY_RULES.items():
        matched_words = [word for word in words if word in query]
        if matched_words:
            filters["category"] = category
            filters["keywords"].extend(matched_words)
            break

    price_match = re.search(
        r"(?:预算\s*)?(\d+)\s*(?:以内|以下|左右|不超过)?|不超过\s*(\d+)",
        query,
    )
    if price_match:
        filters["max_price"] = int(price_match.group(1) or price_match.group(2))

    brand_rules = ["Apple", "苹果", "小米", "华为", "雅诗兰黛", "优衣库", "三顿半"]
    for brand in brand_rules:
        if brand in query:
            filters["brand"] = brand
            break

    return filters


def get_product_price(product: dict[str, Any]) -> float:
    """统一读取商品价格，兼容数据中的 base_price 和 price 字段。"""
    if "base_price" in product:
        return float(product["base_price"])
    if "price" in product:
        return float(product["price"])
    return 0.0


def structured_filter(
    products: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """根据品类、预算和品牌对商品列表做第一轮结构化筛选。"""
    results = []

    for product in products:
        product_category = product.get("category")
        product_brand = product.get("brand", "")
        product_price = get_product_price(product)

        if filters.get("category") and product_category != filters["category"]:
            continue

        if filters.get("max_price") and product_price > filters["max_price"]:
            continue

        if filters.get("brand") and filters["brand"] not in product_brand:
            continue

        results.append(product)

    return results


def choose_candidates(
    products: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """选择候选商品；无结果时按品牌、预算、品类、全库的顺序逐步兜底。"""
    candidates = structured_filter(products, filters)
    if candidates:
        return candidates

    # 兜底 1：先去掉品牌限制，保留品类和预算，避免品牌偏好过窄导致空结果。
    relaxed_filters = dict(filters)
    relaxed_filters["brand"] = None
    candidates = structured_filter(products, relaxed_filters)
    if candidates:
        return candidates

    # 兜底 2：再去掉预算限制，保留品类，让演示优先展示相关商品。
    relaxed_filters["max_price"] = None
    candidates = structured_filter(products, relaxed_filters)
    if candidates:
        return candidates

    # 兜底 3：如果品类下仍无商品，则退回全库检索，最后由 retrieve 再排序。
    return products


def generate_reason(query: str, product: dict[str, Any], evidence: str) -> str:
    """用模板生成中文推荐理由，先保证演示链路稳定。"""
    title = product.get("title", "这款商品")
    return f"{title} 与你的需求「{query}」匹配，{evidence}"


def build_response_item(query: str, retrieved_item: dict[str, Any]) -> dict[str, Any]:
    """把检索结果转换成 Android 商品卡片需要的稳定字段。"""
    product = retrieved_item.get("product", retrieved_item)
    evidence = retrieved_item.get("evidence", "匹配用户需求和商品信息。")

    return {
        "product_id": product.get("product_id", ""),
        "title": product.get("title", ""),
        "brand": product.get("brand", ""),
        "price": get_product_price(product),
        "reason": generate_reason(query, product, evidence),
        "evidence": evidence,
    }


def fallback_items(query: str) -> list[dict[str, Any]]:
    """返回固定 3 张兜底商品卡片，避免 Android 页面因为空结果而无法展示。"""
    return [
        {
            "product_id": "fallback_001",
            "title": "通用推荐商品 1",
            "brand": "系统推荐",
            "price": 0,
            "reason": f"当前根据「{query}」返回兜底推荐，真实检索结果暂不可用。",
            "evidence": "后端兜底逻辑触发。",
        },
        {
            "product_id": "fallback_002",
            "title": "通用推荐商品 2",
            "brand": "系统推荐",
            "price": 0,
            "reason": f"当前根据「{query}」返回兜底推荐，用于保证演示链路不中断。",
            "evidence": "真实推荐链路无结果时返回。",
        },
        {
            "product_id": "fallback_003",
            "title": "通用推荐商品 3",
            "brand": "系统推荐",
            "price": 0,
            "reason": f"当前根据「{query}」返回兜底推荐，后续可替换为真实商品。",
            "evidence": "检索或数据模块不可用时返回。",
        },
    ]


def build_searchable_text(product: dict[str, Any]) -> str:
    """拼接商品可检索文本，供临时 retrieve 做关键词匹配。"""
    return " ".join(
        [
            str(product.get("title", "")),
            str(product.get("brand", "")),
            str(product.get("category", "")),
            str(product.get("sub_category", "")),
            str(product.get("rag_knowledge", {}).get("marketing_description", "")),
        ]
    )


def retrieve(
    query: str,
    candidates: list[dict[str, Any]] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """临时检索函数：按关键词命中数排序，返回带 evidence 的 Top K 商品。"""
    source = products if candidates is None else candidates
    query_terms = extract_filters(query)["keywords"]

    def score_product(product: dict[str, Any]) -> int:
        searchable_text = build_searchable_text(product)
        return sum(1 for term in query_terms if term and term in searchable_text)

    ranked_products = sorted(
        source,
        key=lambda product: (score_product(product), -get_product_price(product)),
        reverse=True,
    )

    results = []
    for product in ranked_products[:top_k]:
        searchable_text = build_searchable_text(product)
        matched_terms = [
            term
            for term in query_terms
            if term and term in searchable_text
        ]
        evidence_terms = "、".join(matched_terms) if matched_terms else "结构化筛选"
        results.append(
            {
                "product": product,
                "evidence": f"临时匹配：命中 {evidence_terms}；来自结构化筛选结果。",
            }
        )

    return results


def recommend_products(
    query: str,
    product_source: list[dict[str, Any]] | None = None,
    top_k: int = 3,
    retrieve_func: Callable[..., list[dict[str, Any]]] = retrieve,
) -> dict[str, Any]:
    """组装完整推荐链路，并在检索为空或异常时返回稳定兜底结果。"""
    try:
        filters = extract_filters(query)
        # None 表示使用默认商品库，空列表表示外部数据源暂时无商品，需要走兜底。
        selected_products = products if product_source is None else product_source
        candidates = choose_candidates(selected_products, filters)
        retrieved_items = retrieve_func(query, candidates=candidates, top_k=top_k)
        items = [
            build_response_item(query, item)
            for item in retrieved_items
        ]

        if not items:
            items = fallback_items(query)

        return {
            "query": query,
            "filters": filters,
            "items": items,
        }
    except Exception as exc:
        return {
            "query": query,
            "filters": {
                "category": EMPTY_FILTERS["category"],
                "max_price": EMPTY_FILTERS["max_price"],
                "brand": EMPTY_FILTERS["brand"],
                "keywords": list(EMPTY_FILTERS["keywords"]),
            },
            "items": fallback_items(query),
            "error": str(exc),
        }
