from recommendation_core.data import load_products
from recommendation_core.filters import extract_filters
from recommendation_core.pipeline import recommend_products
from recommendation_core.ranking import choose_candidates
from recommendation_core.response_builder import build_response_item


def test_recommendation_core_exposes_split_modules():
    filters = extract_filters("预算9000以内，想买拍照好的手机")

    assert filters["category"] == "数码电子"
    assert filters["max_price"] == 9000
    assert "手机" in filters["keywords"]


def test_recommendation_core_keeps_pipeline_behavior():
    product_source = [
        {
            "product_id": "p_1",
            "title": "拍照旗舰手机",
            "brand": "Apple",
            "category": "数码电子",
            "base_price": 8999,
        }
    ]

    response = recommend_products(
        "预算9000以内，想买拍照好的手机",
        product_source=product_source,
        top_k=1,
    )

    assert response["filters"]["category"] == "数码电子"
    assert response["items"][0]["product_id"] == "p_1"
    assert response["items"][0]["reason"]


def test_recommendation_core_keeps_strict_candidate_filtering_and_card_builder():
    product_source = [
        {
            "product_id": "p_1",
            "title": "轻薄办公电脑",
            "brand": "小米",
            "category": "数码电子",
            "price": 4999,
        }
    ]
    filters = {
        "category": "数码电子",
        "max_price": 6000,
        "brand": "Apple",
        "keywords": ["电脑"],
    }

    candidates = choose_candidates(product_source, filters)
    card = build_response_item(
        "预算6000以内的电脑",
        {
            "product": product_source[0],
            "evidence": "命中关键词：电脑",
        },
    )

    assert candidates == []
    assert card["price"] == 4999.0
    assert card["evidence"] == "命中关键词：电脑"


def test_recommendation_core_loads_dataset():
    products = load_products()

    assert len(products) >= 100
    assert products[0]["product_id"]

