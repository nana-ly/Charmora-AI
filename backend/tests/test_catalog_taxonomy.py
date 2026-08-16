import pytest


def test_catalog_taxonomy_aliases_are_unique_and_have_required_fields():
    from agent.catalog_taxonomy import catalog_targets

    alias_to_key: dict[str, str] = {}
    for target in catalog_targets():
        assert target.canonical_key
        assert target.catalog_category
        assert target.aliases
        for alias in target.aliases:
            assert alias not in alias_to_key, f"{alias} maps to multiple targets"
            alias_to_key[alias] = target.canonical_key


def test_catalog_taxonomy_keeps_category_rules_and_filters_consistent():
    from agent.category_rules import detect_target_category
    from recommendation_core.filters import extract_filters

    target = detect_target_category("推荐护肤品")
    filters = extract_filters("推荐护肤品")

    assert target is not None
    assert target.canonical_target_key == "skin_care"
    assert target.catalog_category == "美妆护肤"
    assert filters["category"] == target.catalog_category


def test_catalog_taxonomy_brand_terms_feed_negative_and_recommendation_rules():
    from agent.catalog_taxonomy import brand_terms
    from agent.negative_feedback_rules import BRAND_TERMS
    from recommendation_core.filters import BRAND_RULES

    terms = brand_terms()

    assert "苹果" in terms
    assert "华为" in terms
    assert "雅诗兰黛" in terms
    assert set(BRAND_TERMS).issubset(set(terms))
    assert set(BRAND_RULES).issubset(set(terms))


def test_catalog_taxonomy_golden_queries_keep_existing_rule_outputs():
    from agent.category_rules import detect_target_category
    from agent.negative_feedback_rules import extract_negative_updates
    from recommendation_core.filters import extract_filters

    assert detect_target_category("推荐手机，不要苹果").canonical_target_key == "phone"
    assert extract_negative_updates("推荐手机，不要苹果") == {
        "excluded_brands": ["苹果"]
    }
    assert extract_filters("办公室喝的咖啡")["category"] == "食品生活"
    assert extract_filters("预算9000以内的学生手机") == {
        "category": "数码电子",
        "max_price": 9000,
        "brand": None,
        "keywords": ["手机", "学生"],
    }
    assert extract_negative_updates("不考虑华为") == {"excluded_brands": ["华为"]}


def test_food_dataset_terms_map_to_the_food_catalog_category():
    from agent.category_rules import detect_target_category
    from recommendation_core.filters import extract_filters

    for query in ("我要买吃的", "推荐食品", "想看看零食", "买点方便食品"):
        target = detect_target_category(query)
        assert target is not None
        assert target.canonical_target_key == "food"
        assert target.catalog_category == "食品生活"
        assert extract_filters(query)["category"] == "食品生活"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("可爱的毛绒挂件", "挂件毛绒"),
        ("通勤斜挎包", "包袋收纳"),
        ("宿舍桌面收纳用品", "家居日用"),
        ("开学文具", "文具"),
        ("50元内送同学的礼物", "礼赠组合"),
    ],
)
def test_lifestyle_catalog_categories_are_detectable(query, expected):
    from agent.catalog_taxonomy import detect_catalog_category

    assert detect_catalog_category(query) == expected
