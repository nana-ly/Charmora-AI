"""导购 Agent 商品对比工具。"""

from agent.understanding import ActionResult, AgentAction
from schemas.product import ProductCard


class CompareTool:
    """只基于上一轮推荐结果对比真实商品。"""

    def run(
        self,
        items: list[ProductCard],
        compare_item_indexes: list[int],
    ) -> ActionResult:
        if not items:
            return ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                items=[],
                clarifying_question="我还没有上一轮推荐结果，可以先告诉我想买什么。",
            )

        if len(compare_item_indexes) < 2:
            return ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                items=items,
                clarifying_question="你想比较第几款？可以告诉我两个商品序号。",
            )

        if compare_item_indexes[0] == compare_item_indexes[1]:
            return ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                items=items,
                clarifying_question="你想比较哪两个不同商品？可以告诉我两个不同的序号。",
            )

        # 用户给出的序号必须落在上一轮真实商品列表内，才能进入对比回复。
        if any(index < 1 or index > len(items) for index in compare_item_indexes):
            return ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                items=items,
                clarifying_question=f"上一轮只有 {len(items)} 款商品，你想比较哪两款？",
            )

        return ActionResult(
            action=AgentAction.COMPARE,
            reply_type="compare_reply",
            items=items,
            compare_item_indexes=compare_item_indexes[:2],
        )
