import logging

from fastapi.testclient import TestClient

from agent.graph.runner import LangGraphAgentRunner
from agent.memory import InMemoryConversationStore
from agent.tools import RecommendationTool
from agent.understanding import UserIntent, UserUnderstanding
from core.config import LLMConfig
from llm.reason_service import LLMReasonService
from main import app


client = TestClient(app)


class FakeUnderstandingService:
    def understand(self, *, message, conversation):
        return UserUnderstanding(
            intent=UserIntent.RECOMMEND,
            confidence=0.9,
            purchase_need=message,
            preference_updates={"category": "数码电子"},
        )


def test_recommend_logs_request(monkeypatch, caplog):
    monkeypatch.setenv("RETRIEVER_MODE", "keyword")
    caplog.set_level(logging.INFO)

    response = client.post(
        "/recommend",
        json={"query": "预算9000以内，想买拍照和剪视频好的手机"},
    )

    assert response.status_code == 200
    assert "recommend request received" in caplog.text


def test_langgraph_runner_logs_understood_intent(caplog):
    caplog.set_level(logging.INFO)
    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        understanding_service=FakeUnderstandingService(),
    )

    response = runner.run("test-session", "预算9000以内的拍照手机")

    assert response.session_id == "test-session"
    assert "agent intent understood" in caplog.text


def test_langgraph_runner_logs_turn_id_node_timing_and_no_raw_message(caplog):
    caplog.set_level(logging.INFO)
    raw_message = "预算9000以内的拍照手机-敏感原文不应完整出现"
    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        understanding_service=FakeUnderstandingService(),
    )

    response = runner.run("logging-session", raw_message)

    assert response.session_id == "logging-session"
    assert raw_message not in caplog.text
    assert "turn_id=" in caplog.text
    assert "node=understand_user" in caplog.text
    assert "node=finalize_response" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "result_count=" in caplog.text


def test_chat_logs_x_request_id_without_raw_message(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    raw_message = "完整用户原文不应该写入日志"

    def fake_run_chat(session_id: str, message: str):
        from schemas.chat import ChatResponse

        assert session_id == "api-log-session"
        assert message == raw_message
        return ChatResponse(session_id=session_id, reply="ok", items=[], state={})

    monkeypatch.setattr("api.deps.run_chat", fake_run_chat)

    response = client.post(
        "/chat",
        headers={"X-Request-ID": "req-from-test"},
        json={"session_id": "api-log-session", "message": raw_message},
    )

    assert response.status_code == 200
    assert any(record.request_id == "req-from-test" for record in caplog.records)
    assert any(record.session_id == "api-log-session" for record in caplog.records)
    assert raw_message not in caplog.text


def test_reason_service_logs_when_llm_unavailable(caplog):
    caplog.set_level(logging.DEBUG)
    service = LLMReasonService(LLMConfig(enabled=False, api_key=""))

    reason = service.generate(
        query="预算9000以内的拍照手机",
        product={"title": "拍照旗舰手机"},
        evidence="命中关键词：拍照",
    )

    assert reason
    assert "llm reason generation skipped" in caplog.text
