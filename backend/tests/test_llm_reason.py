from core.config import LLMConfig, load_app_config
from llm.reason_service import LLMReasonService
from recommendation_core import pipeline
from recommendation_core.reason import generate_reason


class FakeLLMClient:
    def __init__(self, response: str):
        self.response = response

    def complete(self, prompt: str) -> str:
        self.prompt = prompt
        return self.response


class FailingLLMClient:
    def complete(self, prompt: str) -> str:
        raise RuntimeError("LLM 调用失败")


class FakeReasonService:
    def __init__(self):
        self.calls = []

    def generate(
        self,
        query: str,
        product: dict,
        evidence: str,
        fallback_reason: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "query": query,
                "product": product,
                "evidence": evidence,
                "fallback_reason": fallback_reason,
            }
        )
        return f"LLM 理由：{product['title']}"


def test_llm_reason_service_uses_template_when_disabled():
    service = LLMReasonService(config=LLMConfig(enabled=False))

    reason = service.generate(
        query="预算9000以内的拍照手机",
        product={"title": "拍照旗舰手机"},
        evidence="命中关键词：拍照",
    )

    assert reason == "拍照旗舰手机 与你的需求「预算9000以内的拍照手机」匹配，命中关键词：拍照"


def test_llm_reason_service_uses_client_when_available():
    client = FakeLLMClient("这款手机适合拍照和预算要求。")
    service = LLMReasonService(
        config=LLMConfig(enabled=True, api_key="test-key"),
        client=client,
    )

    reason = service.generate(
        query="预算9000以内的拍照手机",
        product={"title": "拍照旗舰手机", "brand": "Apple", "base_price": 8999},
        evidence="命中关键词：拍照",
    )

    assert reason == "这款手机适合拍照和预算要求。"
    assert "预算9000以内的拍照手机" in client.prompt
    assert "拍照旗舰手机" in client.prompt


def test_llm_reason_service_falls_back_when_client_fails():
    service = LLMReasonService(
        config=LLMConfig(enabled=True, api_key="test-key"),
        client=FailingLLMClient(),
    )

    reason = service.generate(
        query="预算9000以内的拍照手机",
        product={"title": "拍照旗舰手机"},
        evidence="命中关键词：拍照",
    )

    assert reason == "拍照旗舰手机 与你的需求「预算9000以内的拍照手机」匹配，命中关键词：拍照"


def test_recommendation_reason_accepts_injected_service():
    service = LLMReasonService(
        config=LLMConfig(enabled=True, api_key="test-key"),
        client=FakeLLMClient("LLM 生成的推荐理由。"),
    )

    reason = generate_reason(
        "预算9000以内的拍照手机",
        {"title": "拍照旗舰手机"},
        "命中关键词：拍照",
        reason_service=service,
    )

    assert reason == "LLM 生成的推荐理由。"


def test_load_app_config_reads_dotenv_file(tmp_path, monkeypatch):
    """配置加载应支持读取 .env 文件，便于本地通过环境变量开启 LLM。"""
    for key in [
        "embedding_url",
        "embedding_api",
        "embedding_model",
        "embedding_dimensions",
        "LLM_ENABLED",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_ENABLED=true",
                "LLM_API_KEY=test-key",
                "LLM_BASE_URL=https://example.test/v1",
                "LLM_MODEL=test-model",
                "LLM_TIMEOUT_SECONDS=3",
                "embedding_url=https://embedding.example.test/v1",
                "embedding_api=embedding-key",
                "embedding_model=test-embedding",
                "embedding_dimensions=512",
            ]
        ),
        encoding="utf-8",
    )

    config = load_app_config(env_file=env_file)

    assert config.llm.is_available
    assert config.llm.api_key == "test-key"
    assert config.llm.base_url == "https://example.test/v1"
    assert config.llm.model == "test-model"
    assert config.llm.timeout_seconds == 3
    assert config.rag.embedding_url == "https://embedding.example.test/v1"
    assert config.rag.embedding_api == "embedding-key"
    assert config.rag.embedding_model == "test-embedding"
    assert config.rag.embedding_dimensions == 512


def test_recommend_products_uses_default_llm_reason_service(monkeypatch):
    """推荐链路未显式传入 reason_service 时，应自动创建默认 LLM 理由服务。"""
    service = FakeReasonService()
    monkeypatch.setattr(pipeline, "create_default_reason_service", lambda: service)

    response = pipeline.recommend_products(
        "预算9000以内的拍照手机",
        product_source=[
            {
                "product_id": "p_1",
                "title": "拍照旗舰手机",
                "brand": "Apple",
                "category": "数码电子",
                "base_price": 8999,
            }
        ],
        top_k=1,
    )

    assert response["items"][0]["reason"] == "LLM 理由：拍照旗舰手机"
    assert service.calls[0]["query"] == "预算9000以内的拍照手机"
    assert service.calls[0]["fallback_reason"]

