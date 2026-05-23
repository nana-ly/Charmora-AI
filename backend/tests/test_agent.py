from agent.memory import InMemoryConversationStore
from agent.orchestrator import SimpleAgentRunner
from agent.policy import AgentIntent, AgentPolicy
from agent.tools import RecommendationTool


def test_conversation_store_creates_and_updates_state():
    store = InMemoryConversationStore()

    state = store.get_or_create("session-1")
    state.preferences["category"] = "数码电子"
    store.save(state)

    loaded = store.get_or_create("session-1")

    assert loaded.session_id == "session-1"
    assert loaded.preferences["category"] == "数码电子"


def test_agent_policy_detects_recommend_update_explain_and_clarify():
    policy = AgentPolicy()

    assert policy.detect_intent("预算9000以内的拍照手机").intent == AgentIntent.RECOMMEND
    assert policy.detect_intent("再便宜一点").intent == AgentIntent.UPDATE_PREFERENCE
    assert policy.detect_intent("为什么推荐第一款").intent == AgentIntent.EXPLAIN
    assert policy.detect_intent("你好").intent == AgentIntent.CLARIFY


def test_recommendation_tool_wraps_recommendation_pipeline():
    tool = RecommendationTool()

    result = tool.run("预算9000以内的拍照手机", top_k=2)

    assert result.query == "预算9000以内的拍照手机"
    assert len(result.items) == 2
    assert result.filters.category == "数码电子"


def test_simple_agent_runner_recommends_and_keeps_state():
    runner = SimpleAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        policy=AgentPolicy(),
    )

    response = runner.run("session-1", "预算9000以内的拍照手机")

    assert response.session_id == "session-1"
    assert len(response.items) == 3
    assert response.state["intent"] == AgentIntent.RECOMMEND.value
    assert response.state["preferences"]["category"] == "数码电子"


def test_simple_agent_runner_uses_previous_state_for_follow_up():
    runner = SimpleAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        policy=AgentPolicy(),
    )

    runner.run("session-1", "预算9000以内的拍照手机")
    response = runner.run("session-1", "再便宜一点")

    assert response.state["intent"] == AgentIntent.UPDATE_PREFERENCE.value
    assert response.state["preferences"]["price_preference"] == "lower"
    assert response.items


def test_simple_agent_runner_explains_last_recommendation():
    runner = SimpleAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        policy=AgentPolicy(),
    )

    runner.run("session-1", "预算9000以内的拍照手机")
    response = runner.run("session-1", "为什么推荐第一款")

    assert response.state["intent"] == AgentIntent.EXPLAIN.value
    assert "因为" in response.reply
    assert response.items


def test_simple_agent_runner_clarifies_when_intent_missing():
    runner = SimpleAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        policy=AgentPolicy(),
    )

    response = runner.run("session-1", "你好")

    assert response.state["intent"] == AgentIntent.CLARIFY.value
    assert "预算" in response.reply
    assert response.items == []

