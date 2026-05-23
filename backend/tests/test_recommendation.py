from recommendation import (
    build_response_item,
    choose_candidates,
    extract_filters,
    fallback_items,
    get_product_price,
    load_products,
    products,
    recommend_products,
    retrieve,
    structured_filter,
)


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


def test_choose_candidates_relaxes_brand_then_price_then_all_products():
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

    brand_relaxed = choose_candidates(
        products,
        {
            "category": "数码电子",
            "max_price": 9000,
            "brand": "Apple",
            "keywords": [],
        },
    )
    price_relaxed = choose_candidates(
        products,
        {
            "category": "数码电子",
            "max_price": 5000,
            "brand": None,
            "keywords": [],
        },
    )
    all_products = choose_candidates(
        products,
        {
            "category": "美妆护肤",
            "max_price": 100,
            "brand": "不存在的品牌",
            "keywords": [],
        },
    )

    assert [product["product_id"] for product in brand_relaxed] == ["p_1"]
    assert [product["product_id"] for product in price_relaxed] == ["p_1", "p_2"]
    assert all_products == products


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


def test_retrieve_returns_top_k_candidates_with_evidence():
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

    results = retrieve("想买拍照和剪视频好的手机", candidates=candidates, top_k=2)

    assert len(results) == 2
    assert results[0]["product"]["product_id"] == "p_digital_001"
    assert results[0]["evidence"].startswith("临时匹配")
    assert "拍照" in results[0]["evidence"]


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


def test_fallback_items_returns_three_stable_cards():
    items = fallback_items("完全无法匹配的需求")

    assert len(items) == 3
    assert [item["product_id"] for item in items] == [
        "fallback_001",
        "fallback_002",
        "fallback_003",
    ]
    for item in items:
        assert item["title"]
        assert item["brand"] == "系统推荐"
        assert item["price"] == 0
        assert item["reason"]
        assert item["evidence"]


def test_recommend_products_uses_fallback_when_retrieve_returns_empty():
    def empty_retrieve(
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        return []

    response = recommend_products(
        "找一个不存在的商品",
        product_source=[{"product_id": "p_1", "title": "测试商品"}],
        retrieve_func=empty_retrieve,
    )

    assert len(response["items"]) == 3
    assert response["items"][0]["product_id"] == "fallback_001"
    assert "error" not in response


def test_recommend_products_uses_fallback_when_product_source_is_empty():
    response = recommend_products(
        "预算9000以内的手机",
        product_source=[],
    )

    assert len(response["items"]) == 3
    assert response["items"][0]["product_id"] == "fallback_001"


def test_recommend_products_uses_fallback_when_retrieve_fails():
    def failing_retrieve(
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        raise RuntimeError("检索模块不可用")

    response = recommend_products(
        "预算9000以内的手机",
        product_source=[{"product_id": "p_1", "title": "测试商品"}],
        retrieve_func=failing_retrieve,
    )

    assert len(response["items"]) == 3
    assert response["items"][0]["product_id"] == "fallback_001"
    assert response["error"] == "检索模块不可用"
