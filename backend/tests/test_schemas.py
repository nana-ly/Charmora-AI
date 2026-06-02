from core.config import AppConfig, LLMConfig, RAGConfig
from schemas.chat import ChatRequest, ChatResponse
from schemas.product import ProductCard
from schemas.recommend import (
    ExcludedPriceRange,
    NegativeFilters,
    RecommendFilters,
    RecommendRequest,
    RecommendResponse,
    RecommendationTrace,
    RecommendationTraceItem,
)


def test_recommend_request_accepts_query():
    request = RecommendRequest(query="预算9000以内，想买拍照好的手机")

    assert request.query == "预算9000以内，想买拍照好的手机"
    assert request.debug is False


def test_product_card_contains_android_stable_fields():
    card = ProductCard(
        product_id="p_digital_001",
        title="Apple iPhone 17 Pro",
        brand="Apple",
        price=8999,
        reason="适合重视拍照体验的用户。",
        evidence="匹配关键词：拍照；价格符合预算。",
        image_path="2_数码电子/images/p_digital_001_live.jpg",
        image_url="/assets/products/2_%E6%95%B0%E7%A0%81%E7%94%B5%E5%AD%90/images/p_digital_001_live.jpg",
    )

    assert card.model_dump() == {
        "product_id": "p_digital_001",
        "title": "Apple iPhone 17 Pro",
        "brand": "Apple",
        "price": 8999.0,
        "reason": "适合重视拍照体验的用户。",
        "evidence": "匹配关键词：拍照；价格符合预算。",
        "image_path": "2_数码电子/images/p_digital_001_live.jpg",
        "image_url": "/assets/products/2_%E6%95%B0%E7%A0%81%E7%94%B5%E5%AD%90/images/p_digital_001_live.jpg",
        "imageUrl": "/assets/products/2_%E6%95%B0%E7%A0%81%E7%94%B5%E5%AD%90/images/p_digital_001_live.jpg",
    }


def test_recommend_response_wraps_filters_and_items():
    response = RecommendResponse(
        query="想买手机",
        filters=RecommendFilters(category="数码电子", keywords=["手机"]),
        result_count=8,
        items=[
            ProductCard(
                product_id="p_digital_001",
                title="Apple iPhone 17 Pro",
                brand="Apple",
                price=8999,
                reason="适合拍照。",
                evidence="命中手机。",
            )
        ],
    )

    assert response.filters.category == "数码电子"
    assert response.filters.max_price is None
    assert response.result_count == 8
    assert response.result_count > len(response.items)
    assert response.items[0].product_id == "p_digital_001"
    assert response.trace is None


def test_recommend_response_defaults_result_count_to_item_count():
    response = RecommendResponse(
        query="想买手机",
        filters=RecommendFilters(category="数码电子"),
        items=[
            ProductCard(
                product_id="p_digital_001",
                title="Apple iPhone 17 Pro",
                brand="Apple",
                price=8999,
                reason="适合拍照。",
                evidence="命中手机。",
            )
        ],
    )

    assert response.result_count == 1


def test_recommendation_trace_schema_keeps_debug_fields_optional():
    trace = RecommendationTrace(
        retriever_mode="keyword",
        query_length=5,
        top_k=3,
        source_count=10,
        structured_candidate_count=4,
        negative_filtered_candidate_count=3,
        retrieved_count=2,
        final_count=1,
        negative_filter_applied=True,
        items=[
            RecommendationTraceItem(
                product_id="p_1",
                title="测试商品",
                brand="测试品牌",
                rank=1,
                score=0.8,
                score_type="keyword_weighted_match",
                source="keyword",
                evidence="命中手机。",
                retriever_mode="keyword",
            )
        ],
        dropped=[{"product_id": "p_2", "reason": "negative_filter"}],
    )

    dumped = trace.model_dump()

    assert dumped["items"][0]["product_id"] == "p_1"
    assert dumped["dropped"] == [{"product_id": "p_2", "reason": "negative_filter"}]


def test_negative_filters_defaults_are_empty_lists():
    filters = NegativeFilters()

    assert filters.excluded_product_ids == []
    assert filters.excluded_brands == []
    assert filters.excluded_keywords == []
    assert filters.excluded_price_ranges == []


def test_excluded_price_range_is_reserved_schema():
    price_range = ExcludedPriceRange(
        min_price=1000,
        max_price=2000,
        reason="测试区间",
        source_product_id="p_1",
    )

    assert price_range.min_price == 1000
    assert price_range.max_price == 2000
    assert price_range.reason == "测试区间"
    assert price_range.source_product_id == "p_1"


def test_chat_request_and_response_keep_session_shape():
    request = ChatRequest(session_id="s_001", message="我想买拍照好的手机")
    response = ChatResponse(
        session_id=request.session_id,
        reply="可以，我先帮你按拍照需求筛选。",
        result_count=6,
        items=[],
        state={"intent": "recommend", "preferences": {"category": "数码电子"}},
    )

    assert request.session_id == "s_001"
    assert request.message == "我想买拍照好的手机"
    assert response.result_count == 6
    assert response.state["intent"] == "recommend"


def test_app_config_has_safe_defaults():
    config = AppConfig()

    assert config.agent_runner == "langgraph"
    assert config.retriever_mode == "vector"
    assert config.default_top_k == 3
    assert config.llm.enabled is False
    assert config.llm.is_available is False
    assert config.rag.embedding_model == "text-embedding-v4"
    assert config.rag.embedding_dimensions == 1024


def test_rag_config_keeps_embedding_settings():
    config = RAGConfig(
        embedding_url="https://example.test/v1",
        embedding_api="test-key",
        embedding_model="test-embedding",
        embedding_dimensions=512,
    )

    assert config.embedding_url == "https://example.test/v1"
    assert config.embedding_api == "test-key"
    assert config.embedding_model == "test-embedding"
    assert config.embedding_dimensions == 512


def test_llm_config_available_only_when_enabled_with_api_key():
    disabled = LLMConfig(enabled=False, api_key="sk-test")
    missing_key = LLMConfig(enabled=True, api_key="")
    available = LLMConfig(enabled=True, api_key="sk-test")

    assert disabled.is_available is False
    assert missing_key.is_available is False
    assert available.is_available is True


def test_config_docstrings_do_not_advertise_vector_keyword_fallback():
    from core import config as config_module

    assert "回退到本地关键词检索" not in (config_module.__doc__ or "")


def test_removed_unused_schema_models_are_not_available():
    import schemas.chat as chat_schema
    import schemas.product as product_schema

    assert not hasattr(chat_schema, "ConversationStateSnapshot")
    assert not hasattr(product_schema, "RetrievedProduct")
