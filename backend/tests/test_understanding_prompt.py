import logging


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, messages, max_tokens=160):
        return FakeResponse(self.content)


def test_understanding_prompt_loads_versioned_markdown_template():
    from agent.prompt_loader import load_prompt

    template = load_prompt("understanding_v1")

    assert template.version == "understanding_v1"
    assert "Return one JSON object only" in template.content
    assert "negative_updates" in template.content
    assert "is_broad_category_request" in template.content
    assert "restore_context_category" in template.content


def test_understanding_prompt_loader_falls_back_when_template_missing(caplog):
    from agent.prompt_loader import DEFAULT_UNDERSTANDING_PROMPT, load_prompt

    with caplog.at_level(logging.WARNING):
        template = load_prompt("missing_prompt")

    assert template.version == "missing_prompt"
    assert template.content == DEFAULT_UNDERSTANDING_PROMPT
    assert "prompt load failed" in caplog.text


def test_llm_understanding_service_exposes_prompt_version_and_uses_loader():
    from agent.memory import ConversationState
    from agent.prompt_loader import PromptTemplate
    from agent.understanding import LLMUserUnderstandingService

    def fake_loader(name: str) -> PromptTemplate:
        return PromptTemplate(version=name, content="Return one JSON object only")

    service = LLMUserUnderstandingService(
        llm=FakeLLM('{"intent":"clarify","confidence":0.8}'),
        prompt_version="understanding_v1",
        prompt_loader=fake_loader,
    )

    service.understand(
        message="你好",
        conversation=ConversationState(session_id="prompt-version"),
    )

    assert service.prompt_version == "understanding_v1"


def test_llm_parse_failure_logs_prompt_version(caplog):
    from agent.memory import ConversationState
    from agent.understanding import LLMUserUnderstandingService

    service = LLMUserUnderstandingService(
        llm=FakeLLM("不是 JSON"),
        prompt_version="understanding_v1",
    )

    with caplog.at_level(logging.ERROR):
        service.understand(
            message="推荐手机",
            conversation=ConversationState(session_id="prompt-parse-error"),
        )

    assert "prompt_version=understanding_v1" in caplog.text
