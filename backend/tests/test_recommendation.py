import pytest

from recommendation_core.data import load_products, products
from recommendation_core.filters import extract_filters
from recommendation_core.pipeline import recommend_products
from recommendation_core.ranking import choose_candidates, get_product_price, structured_filter
from recommendation_core.response_builder import build_response_item
from retrieval.base import RetrievalResult
from retrieval.keyword import KeywordRetriever
from schemas.recommend import NegativeFilters


class FakeEmptyRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        return []


class FakeResultRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        return [
            RetrievalResult(
                product=candidates[0],
                evidence="测试 evidence",
                score=1.0,
            )
        ][:top_k]


class FakeFailingRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        raise RuntimeError("检索模块不可用")


class CapturingRetriever:
    def __init__(self):
        self.candidates = None

    def search(self, query: str, candidates=None, top_k: int = 3):
        self.candidates = list(candidates or [])
        return [
            RetrievalResult(
                product=product,
                evidence="test evidence",
                score=1.0,
            )
            for product in self.candidates[:top_k]
        ]


class IgnoringCandidateRetriever:
    def __init__(self, products):
        self.products = products

    def search(self, query: str, candidates=None, top_k: int = 3):
        return [
            RetrievalResult(
                product=product,
                evidence="test evidence",
                score=1.0,
            )
            for product in self.products[:top_k]
        ]


def test_extract_filters_parses_category_budget_and_keywords():
    filters = extract_filters("预算9000以内，想买拍照和剪视频好的手机")

    assert filters == {
        "category": "数码电子",
        "max_price": 9000,
        "brand": None,
        "keywords": ["手机", "拍照", "剪视频"],
    }


def test_extract_filters_parses_brand_preference():
    filters = extract_filters("想买苹果手机，预算9000以内")

    assert filters["brand"] == "苹果"


def test_extract_filters_maps_skin_care_terms_to_beauty_category():
    from recommendation_core.filters import extract_filters

    for query in ("推荐护肤品", "推荐美妆", "推荐化妆品"):
        filters = extract_filters(query)
        assert filters["category"] == "美妆护肤"


def test_extract_filters_supports_extended_keywords_and_budget_patterns():
    filters = extract_filters("预算9000想买续航好的学生手机")
    reversed_budget_filters = extract_filters("不超过9000的拍照手机")

    assert filters["category"] == "数码电子"
    assert filters["max_price"] == 9000
    assert "续航" in filters["keywords"]
    assert "学生" in filters["keywords"]
    assert reversed_budget_filters["max_price"] == 9000


def test_get_product_price_supports_base_price_and_price():
    assert get_product_price({"base_price": "5999"}) == 5999.0
    assert get_product_price({"price": 6999}) == 6999.0
    assert get_product_price({}) == 0.0


def test_structured_filter_filters_by_category_budget_and_brand():
    products = [
        {
            "product_id": "p_1",
            "category": "数码电子",
            "brand": "Apple",
            "price": 8999,
        },
        {
            "product_id": "p_2",
            "category": "数码电子",
            "brand": "Apple",
            "price": 9999,
        },
        {
            "product_id": "p_3",
            "category": "食品生活",
            "brand": "Apple",
            "price": 99,
        },
    ]
    filters = {
        "category": "数码电子",
        "max_price": 9000,
        "brand": "Apple",
        "keywords": [],
    }

    results = structured_filter(products, filters)

    assert [product["product_id"] for product in results] == ["p_1"]


def test_choose_candidates_applies_filters_without_relaxing_constraints():
    products = [
        {
            "product_id": "p_1",
            "category": "数码电子",
            "brand": "小米",
            "price": 5999,
        },
        {
            "product_id": "p_2",
            "category": "数码电子",
            "brand": "Apple",
            "price": 9999,
        },
    ]

    brand_mismatch = choose_candidates(
        products,
        {
            "category": "数码电子",
            "max_price": 9000,
            "brand": "Apple",
            "keywords": [],
        },
    )
    budget_mismatch = choose_candidates(
        products,
        {
            "category": "数码电子",
            "max_price": 5000,
            "brand": None,
            "keywords": [],
        },
    )
    category_mismatch = choose_candidates(
        products,
        {
            "category": "美妆护肤",
            "max_price": 100,
            "brand": "不存在的品牌",
            "keywords": [],
        },
    )

    assert brand_mismatch == []
    assert budget_mismatch == []
    assert category_mismatch == []


def test_build_response_item_converts_retrieved_result_to_card_fields():
    item = build_response_item(
        "预算9000以内，想买拍照好的手机",
        {
            "product": {
                "product_id": "p_digital_001",
                "title": "Apple iPhone 17 Pro",
                "brand": "Apple",
                "base_price": 8999,
            },
            "evidence": "匹配关键词：拍照；价格符合预算。",
        },
    )

    assert item == {
        "product_id": "p_digital_001",
        "title": "Apple iPhone 17 Pro",
        "brand": "Apple",
        "price": 8999.0,
        "reason": "Apple iPhone 17 Pro 与你的需求「预算9000以内，想买拍照好的手机」匹配，匹配关键词：拍照；价格符合预算。",
        "evidence": "匹配关键词：拍照；价格符合预算。",
    }


def test_load_products_reads_dataset_json_files():
    loaded_products = load_products()

    assert len(loaded_products) >= 100
    assert loaded_products[0]["product_id"]
    assert loaded_products[0]["title"]
    assert loaded_products[0]["brand"]
    assert loaded_products[0]["category"]
    assert "base_price" in loaded_products[0]


def test_products_global_is_available_for_recommend_flow():
    assert len(products) >= 100


def test_keyword_retriever_returns_top_k_candidates_with_evidence():
    retriever = KeywordRetriever()
    candidates = [
        {
            "product_id": "p_digital_001",
            "title": "拍照旗舰手机",
            "brand": "Apple",
            "category": "数码电子",
            "base_price": 8999,
        },
        {
            "product_id": "p_digital_002",
            "title": "降噪耳机",
            "brand": "Sony",
            "category": "数码电子",
            "base_price": 1999,
        },
        {
            "product_id": "p_digital_003",
            "title": "视频剪辑手机",
            "brand": "小米",
            "category": "数码电子",
            "base_price": 5999,
        },
    ]

    results = retriever.search("想买拍照和剪视频好的手机", candidates=candidates, top_k=2)

    assert len(results) == 2
    assert results[0].product["product_id"] == "p_digital_003"
    assert results[0].evidence.startswith("临时匹配")
    assert "剪视频" in results[0].evidence


def test_recommend_products_assembles_real_recommendation_chain():
    product_source = [
        {
            "product_id": "p_digital_001",
            "title": "拍照旗舰手机",
            "brand": "Apple",
            "category": "数码电子",
            "base_price": 8999,
        },
        {
            "product_id": "p_digital_002",
            "title": "剪视频性能手机",
            "brand": "小米",
            "category": "数码电子",
            "base_price": 5999,
        },
        {
            "product_id": "p_digital_003",
            "title": "长续航学生手机",
            "brand": "华为",
            "category": "数码电子",
            "base_price": 3999,
        },
    ]

    response = recommend_products(
        "预算9000以内，想买拍照和剪视频好的手机",
        product_source=product_source,
        top_k=3,
    )

    assert response["query"] == "预算9000以内，想买拍照和剪视频好的手机"
    assert response["filters"]["category"] == "数码电子"
    assert response["filters"]["max_price"] == 9000
    assert len(response["items"]) == 3
    assert response["items"][0]["product_id"].startswith("p_digital_")
    assert response["items"][0]["reason"]
    assert response["items"][0]["evidence"].startswith("临时匹配")


def test_recommend_products_consumes_retriever_results_directly():
    response = recommend_products(
        "预算9000以内的测试商品",
        product_source=[
            {
                "product_id": "p_1",
                "title": "测试商品",
                "brand": "测试品牌",
                "category": "数码电子",
                "base_price": 100,
            }
        ],
        retriever=FakeResultRetriever(),
    )

    assert response["items"][0]["product_id"] == "p_1"
    assert response["items"][0]["evidence"] == "测试 evidence"


def test_recommend_products_filters_excluded_product_ids_before_retrieval():
    product_source = [
        {
            "product_id": "p_1",
            "title": "Huawei camera phone",
            "brand": "华为",
            "category": "数码电子",
            "base_price": 4999,
        },
        {
            "product_id": "p_2",
            "title": "Apple camera phone",
            "brand": "苹果",
            "category": "数码电子",
            "base_price": 5999,
        },
    ]
    retriever = CapturingRetriever()

    response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=2,
        retriever=retriever,
        negative_filters=NegativeFilters(excluded_product_ids=["p_1"]),
    )

    assert [product["product_id"] for product in retriever.candidates] == ["p_2"]
    assert [item["product_id"] for item in response["items"]] == ["p_2"]


def test_recommend_products_filters_excluded_brands_before_retrieval():
    product_source = [
        {
            "product_id": "p_1",
            "title": "Apple camera phone",
            "brand": " Apple ",
            "category": "数码电子",
            "base_price": 4999,
        },
        {
            "product_id": "p_2",
            "title": "Huawei camera phone",
            "brand": "苹果",
            "category": "数码电子",
            "base_price": 5999,
        },
    ]
    retriever = CapturingRetriever()

    response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=2,
        retriever=retriever,
        negative_filters=NegativeFilters(excluded_brands=["apple"]),
    )

    assert [product["product_id"] for product in retriever.candidates] == ["p_2"]
    assert [item["product_id"] for item in response["items"]] == ["p_2"]


def test_recommend_products_final_filter_removes_retriever_violations():
    product_source = [
        {
            "product_id": "p_2",
            "title": "Apple camera phone",
            "brand": "苹果",
            "category": "数码电子",
            "base_price": 5999,
        }
    ]
    retriever = IgnoringCandidateRetriever(
        [
            {
                "product_id": "p_1",
                "title": "Huawei camera phone",
                "brand": "华为",
                "category": "数码电子",
                "base_price": 4999,
            },
            product_source[0],
        ]
    )

    response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=2,
        retriever=retriever,
        negative_filters=NegativeFilters(excluded_product_ids=["p_1"]),
    )

    assert [item["product_id"] for item in response["items"]] == ["p_2"]


def test_recommend_products_returns_no_results_after_final_negative_filter():
    product_source = [
        {
            "product_id": "p_2",
            "title": "Apple camera phone",
            "brand": "苹果",
            "category": "数码电子",
            "base_price": 5999,
        }
    ]
    retriever = IgnoringCandidateRetriever(
        [
            {
                "product_id": "p_1",
                "title": "Huawei camera phone",
                "brand": " 华为 ",
                "category": "数码电子",
                "base_price": 4999,
            }
        ]
    )

    response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=1,
        retriever=retriever,
        negative_filters=NegativeFilters(excluded_brands=["华为"]),
    )

    assert response["items"] == []


def test_recommend_products_returns_empty_items_when_retriever_returns_empty():
    response = recommend_products(
        "找一个不存在的商品",
        product_source=[{"product_id": "p_1", "title": "测试商品"}],
        retriever=FakeEmptyRetriever(),
    )

    assert response["items"] == []
    assert "error" not in response


def test_recommend_products_returns_empty_items_when_product_source_is_empty():
    response = recommend_products(
        "预算9000以内的手机",
        product_source=[],
    )

    assert response["items"] == []


def test_recommend_products_propagates_retriever_errors():
    with pytest.raises(RuntimeError, match="检索模块不可用"):
        recommend_products(
            "预算9000以内的手机",
            product_source=[{"product_id": "p_1", "title": "测试商品"}],
            retriever=FakeFailingRetriever(),
        )
