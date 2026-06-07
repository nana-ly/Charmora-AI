"""构造用户理解 LLM 的上下文提示块。"""

from __future__ import annotations

import json

from agent.memory import ConversationState
from schemas.product import ProductCard


class PromptContextBuilder:
    """把 ConversationState 转成理解层 prompt 需要的紧凑文本。"""

    def __init__(
        self,
        *,
        recent_message_limit: int = 8,
        last_item_limit: int | None = None,
        evidence_max_chars: int | None = None,
    ) -> None:
        self.recent_message_limit = recent_message_limit
        self.last_item_limit = last_item_limit
        self.evidence_max_chars = evidence_max_chars

    def build(self, message: str, conversation: ConversationState) -> str:
        """生成 LLM user message，默认保持原理解层上下文内容不变。"""
        return (
            f"最新用户消息：{message}\n"
            f"最近对话：\n{self._recent_history(conversation)}\n"
            f"当前 purchase_need：{conversation.purchase_need or '无'}\n"
            f"当前 preferences：{json.dumps(conversation.preferences, ensure_ascii=False)}\n"
            f"排除品牌：{json.dumps(conversation.excluded_brands, ensure_ascii=False)}\n"
            f"pending_restore_category：{conversation.pending_restore_category or '无'}\n"
            f"previous_purchase_contexts：\n{self._previous_contexts(conversation)}\n"
            f"上一轮成功推荐：\n{self._previous_items(conversation)}"
        )

    def _recent_history(self, conversation: ConversationState) -> str:
        recent_messages = conversation.messages[-self.recent_message_limit :]
        history = "\n".join(
            f"{item.role}: {item.content}"
            for item in recent_messages
            if item.content.strip()
        )
        return history or "无"

    def _previous_contexts(self, conversation: ConversationState) -> str:
        # 历史购买上下文只给品类和需求摘要，避免把旧商品结果再次注入理解 prompt。
        previous_contexts = "\n".join(
            (
                f"- target_category={item.target_category or '无'}; "
                f"category={item.category or '无'}; "
                f"purchase_need={item.purchase_need}"
            )
            for item in conversation.previous_purchase_contexts
        )
        return previous_contexts or "无"

    def _previous_items(self, conversation: ConversationState) -> str:
        items = conversation.last_items
        if self.last_item_limit is not None:
            items = items[: self.last_item_limit]
        previous_items = "\n".join(
            self._format_previous_item(index, item)
            for index, item in enumerate(items, start=1)
        )
        return previous_items or "无"

    def _format_previous_item(self, index: int, item: ProductCard) -> str:
        evidence = item.evidence
        if self.evidence_max_chars is not None and len(evidence) > self.evidence_max_chars:
            evidence = f"{evidence[: self.evidence_max_chars]}..."
        return (
            f"{index}. title={item.title}; brand={item.brand}; "
            f"price={item.price}; evidence={evidence}"
        )
