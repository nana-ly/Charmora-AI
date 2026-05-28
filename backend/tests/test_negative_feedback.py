from agent.negative_feedback_rules import extract_negative_updates


def test_negative_rules_detect_arabic_item_index_exclusion():
    assert extract_negative_updates("不要第 2 个") == {"excluded_item_indexes": [2]}
    assert extract_negative_updates("排除第2款") == {"excluded_item_indexes": [2]}
    assert extract_negative_updates("第 3 个不要") == {"excluded_item_indexes": [3]}
    assert extract_negative_updates("不要第2个也可以") == {"excluded_item_indexes": [2]}


def test_negative_rules_do_not_parse_chinese_item_index():
    assert extract_negative_updates("排除第二款") == {
        "unsupported_negative_type": "item_index_chinese_number"
    }


def test_negative_rules_detect_brand_exclusion_and_removal_text():
    assert extract_negative_updates("不要苹果") == {"excluded_brands": ["苹果"]}
    assert extract_negative_updates("不考虑华为") == {"excluded_brands": ["华为"]}
    assert extract_negative_updates("苹果也可以") == {"remove_excluded_brands": ["苹果"]}
    assert extract_negative_updates("取消排除苹果") == {"remove_excluded_brands": ["苹果"]}


def test_negative_rules_brand_exclusion_wins_for_ambiguous_removal_text():
    assert extract_negative_updates("不要苹果也可以") == {"excluded_brands": ["苹果"]}
    assert extract_negative_updates("苹果也可以不要") == {"excluded_brands": ["苹果"]}


def test_negative_rules_do_not_treat_price_feedback_as_brand_exclusion():
    assert extract_negative_updates("苹果手机不要这么贵") == {}


def test_negative_rules_mark_item_removal_as_unsupported_for_mvp():
    assert extract_negative_updates("第 2 个也可以") == {
        "remove_excluded_item_indexes": [2],
        "unsupported_negative_type": "remove_item_index",
    }
