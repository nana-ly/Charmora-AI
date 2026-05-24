"""Agent 意图判断策略。"""

from enum import Enum

from pydantic import BaseModel


class AgentIntent(str, Enum):
    """Agent 当前支持的意图集合。"""

    RECOMMEND = "recommend"
    UPDATE_PREFERENCE = "update_preference"
    EXPLAIN = "explain"
    CLARIFY = "clarify"


class AgentDecision(BaseModel):
    """意图判断结果。"""

    intent: AgentIntent
    confidence: float = 1.0


class AgentPolicy:
    """规则版意图策略。

    当前先用透明规则保证可测试；后续可替换为 LLM 意图识别，但仍返回 AgentDecision。
    """

    _recommend_keywords = [
        "买",
        "推荐",
        "预算",
        "手机",
        "耳机",
        "电脑",
        "护肤",
        "咖啡",
        "衣",
    ]
    _update_keywords = ["再便宜", "便宜一点", "换一个", "更低", "贵了"]
    _explain_keywords = ["为什么", "原因", "解释", "怎么推荐"]

    def detect_intent(self, message: str) -> AgentDecision:
        """根据用户消息判断下一步动作。"""
        if any(keyword in message for keyword in self._explain_keywords):
            return AgentDecision(intent=AgentIntent.EXPLAIN)

        if any(keyword in message for keyword in self._update_keywords):
            return AgentDecision(intent=AgentIntent.UPDATE_PREFERENCE)

        if any(keyword in message for keyword in self._recommend_keywords):
            return AgentDecision(intent=AgentIntent.RECOMMEND)

        return AgentDecision(intent=AgentIntent.CLARIFY, confidence=0.6)

