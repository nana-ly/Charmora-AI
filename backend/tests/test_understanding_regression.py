import json
from pathlib import Path

from core.config import LLMConfig


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, messages, max_tokens=160):
        return FakeResponse(self.content)


def _load_cases():
    path = Path(__file__).parent / "fixtures" / "understanding_cases.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _conversation_from_case(case):
    from agent.memory import ConversationState

    return ConversationState.model_validate(case["conversation"])


def test_understanding_regression_cases_do_not_call_real_llm():
    from agent.understanding import LLMUserUnderstandingService

    for case in _load_cases():
        if case.get("llm_unavailable"):
            service = LLMUserUnderstandingService(
                config=LLMConfig(enabled=False, api_key="")
            )
        else:
            service = LLMUserUnderstandingService(llm=FakeLLM(case["llm_content"]))

        understanding = service.understand(
            message=case["message"],
            conversation=_conversation_from_case(case),
        )

        assert understanding.intent.value == case["expected_intent"], case["name"]
        for key, value in case["expected_preference_updates"].items():
            assert understanding.preference_updates.get(key) == value, case["name"]
        assert understanding.negative_updates == case["expected_negative_updates"]
