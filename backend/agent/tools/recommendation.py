"""导购 Agent 推荐工具。"""

import inspect
from collections.abc import Callable
from typing import Any

from recommendation_core.pipeline import recommend_products
from schemas.recommend import NegativeFilters, RecommendFilters, RecommendResponse


class RecommendationTool:
    """推荐链的轻量封装，统一输出结构化推荐响应。"""

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
        include_trace: bool = False,
    ) -> RecommendResponse:
        """调用推荐链，并把字典结果规范化为结构化响应。"""
        kwargs: dict[str, Any] = {"top_k": top_k}
        if negative_filters is not None and self._accepts_negative_filters():
            kwargs["negative_filters"] = negative_filters
        if include_trace and self._accepts_include_trace():
            kwargs["include_trace"] = include_trace

        result = self.recommend_func(query, **kwargs)
        return RecommendResponse(
            query=result["query"],
            filters=RecommendFilters(**result["filters"]),
            items=result["items"],
            trace=result.get("trace"),
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

    def _accepts_include_trace(self) -> bool:
        signature = inspect.signature(self.recommend_func)
        return (
            "include_trace" in signature.parameters
            or any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
        )
