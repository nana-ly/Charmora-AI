from core.config import LLMConfig
from llm.reason_service import LLMReasonService
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

