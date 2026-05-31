"""Agent 可调用工具。"""

import inspect
from collections.abc import Callable
from typing import Any

from agent.understanding import ActionResult, AgentAction
from recommendation_core.pipeline import recommend_products
from schemas.product import ProductCard
from schemas.recommend import NegativeFilters, RecommendFilters, RecommendResponse


class RecommendationTool:
    """推荐链的轻量封装。"""

    def __init__(
        self,
        recommend_func: Callable[..., dict[str, Any]] = recommend_products,
    ) -> None:
        self.recommend_func = recommend_func

    def run(
        self,
        query: str,
        top_k: int = 3,
        negative_filters: NegativeFilters | None = None,
    ) -> RecommendResponse:
        """调用推荐链并规范化结构化响应。"""
        kwargs: dict[str, Any] = {"top_k": top_k}
        if negative_filters is not None and self._accepts_negative_filters():
            kwargs["negative_filters"] = negative_filters

        result = self.recommend_func(query, **kwargs)
        return RecommendResponse(
            query=result["query"],
            filters=RecommendFilters(**result["filters"]),
            items=result["items"],
        )

    def _accepts_negative_filters(self) -> bool:
        signature = inspect.signature(self.recommend_func)
        return (
            "negative_filters" in signature.parameters
            or any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
        )


class ExplainTool:
    """从上一轮推荐结果中选择需要解释的商品。"""

    def run(
        self,
        *,
        items: list[ProductCard],
        target_item_index: int | None,
        fallback_item_index: int | None = None,
    ) -> ActionResult:
        """只解释已有商品，避免让模型凭空生成商品事实。"""
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


class CompareTool:
    """对上一轮推荐结果做对比，只复用已有商品信息。"""

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

        # compare_item_indexes 来自用户表达，使用前必须限定在上一轮商品序号范围内。
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
