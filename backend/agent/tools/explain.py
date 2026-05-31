"""导购 Agent 解释工具。"""

from agent.understanding import ActionResult, AgentAction
from schemas.product import ProductCard


class ExplainTool:
    """从上一轮推荐结果中选择需要解释的真实商品。"""

    def run(
        self,
        *,
        items: list[ProductCard],
        target_item_index: int | None,
        fallback_item_index: int | None = None,
    ) -> ActionResult:
        """只解释已有商品，避免凭空生成商品事实。"""
        if not items:
            return ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                items=[],
                clarifying_question="我还没有上一轮推荐结果，可以先告诉我品类、预算和偏好。",
            )

        selected_index = target_item_index or fallback_item_index or 1
        zero_based_index = selected_index - 1
        if zero_based_index < 0 or zero_based_index >= len(items):
            return ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                items=items,
                clarifying_question="你想了解第几款商品？可以告诉我对应序号。",
            )

        return ActionResult(
            action=AgentAction.EXPLAIN,
            reply_type="explain_reply",
            items=items,
            target_item_index=selected_index,
        )
