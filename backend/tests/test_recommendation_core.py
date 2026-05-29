from recommendation_core.data import load_products
from recommendation_core.filters import extract_filters
from recommendation_core.negative_filter import passes_negative_filter
from recommendation_core.pipeline import recommend_products
from recommendation_core.ranking import choose_candidates
from recommendation_core.response_builder import build_response_item
from schemas.recommend import NegativeFilters


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


def test_recommendation_core_negative_filters_none_and_empty_are_equivalent():
    product_source = [
        {
            "product_id": "p_1",
            "title": "Apple camera phone",
            "brand": "苹果",
            "category": "数码电子",
            "base_price": 5999,
        }
    ]

    default_response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=1,
    )
    none_response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=1,
        negative_filters=None,
    )
    empty_response = recommend_products(
        "camera phone under 7000",
        product_source=product_source,
        top_k=1,
        negative_filters=NegativeFilters(),
    )

    assert none_response == default_response
    assert empty_response == default_response


def test_negative_filter_excludes_composite_brand_by_whitespace_token():
    product = {"product_id": "p_1", "brand": "Apple 苹果"}
    negative_filters = NegativeFilters(excluded_brands=["苹果"])

    assert passes_negative_filter(product, negative_filters) is False


def test_negative_filter_does_not_exclude_composite_brand_by_substring():
    product = {"product_id": "p_1", "brand": "Apple 苹果"}
    negative_filters = NegativeFilters(excluded_brands=["苹"])

    assert passes_negative_filter(product, negative_filters) is True


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

