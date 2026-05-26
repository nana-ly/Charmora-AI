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
        "精华",
        "面霜",
        "洁面",
        "防晒",
        "敏感肌",
        "抗初老",
        "T恤",
        "通勤",
        "凉快",
        "穿",
        "速溶",
        "食品",
    ]
    _product_need_keywords = [
        "能用",
        "适合",
        "好用",
        "想要",
        "需要",
        "以内",
        "抗初老",
        "通勤",
        "凉快",
    ]
    _product_category_keywords = [
        "手机",
        "耳机",
        "电脑",
        "护肤",
        "咖啡",
        "衣",
        "精华",
        "面霜",
        "洁面",
        "防晒",
        "T恤",
        "食品",
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

        # 用户常用“敏感肌能用的抗初老精华”这类省略句表达商品需求。
        # 这类句子没有“买/推荐/预算”，但同时包含商品属性和品类，应进入推荐链路。
        has_product_need = any(keyword in message for keyword in self._product_need_keywords)
        has_product_category = any(keyword in message for keyword in self._product_category_keywords)
        if has_product_need and has_product_category:
            return AgentDecision(intent=AgentIntent.RECOMMEND)

        return AgentDecision(intent=AgentIntent.CLARIFY, confidence=0.6)

