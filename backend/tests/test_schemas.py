from core.config import AppConfig, LLMConfig, RAGConfig
from schemas.chat import ChatRequest, ChatResponse
from schemas.product import ProductCard
from schemas.recommend import RecommendFilters, RecommendRequest, RecommendResponse


def test_recommend_request_accepts_query():
    request = RecommendRequest(query="预算9000以内，想买拍照好的手机")

    assert request.query == "预算9000以内，想买拍照好的手机"


def test_product_card_contains_android_stable_fields():
    card = ProductCard(
        product_id="p_digital_001",
        title="Apple iPhone 17 Pro",
        brand="Apple",
        price=8999,
        reason="适合重视拍照体验的用户。",
        evidence="匹配关键词：拍照；价格符合预算。",
    )

    assert card.model_dump() == {
        "product_id": "p_digital_001",
        "title": "Apple iPhone 17 Pro",
        "brand": "Apple",
        "price": 8999.0,
        "reason": "适合重视拍照体验的用户。",
        "evidence": "匹配关键词：拍照；价格符合预算。",
    }


def test_recommend_response_wraps_filters_and_items():
    response = RecommendResponse(
        query="想买手机",
        filters=RecommendFilters(category="数码电子", keywords=["手机"]),
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
    assert response.items[0].product_id == "p_digital_001"


def test_chat_request_and_response_keep_session_shape():
    request = ChatRequest(session_id="s_001", message="我想买拍照好的手机")
    response = ChatResponse(
        session_id=request.session_id,
        reply="可以，我先帮你按拍照需求筛选。",
        items=[],
        state={"intent": "recommend", "preferences": {"category": "数码电子"}},
    )

    assert request.session_id == "s_001"
    assert request.message == "我想买拍照好的手机"
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
