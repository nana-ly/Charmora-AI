import pytest


@pytest.fixture(autouse=True)
def disable_real_llm_by_default(monkeypatch):
    """测试默认禁用真实 LLM，避免本地 .env 中的密钥触发外部请求。"""
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "8")

