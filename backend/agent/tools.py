"""Agent callable tools."""

import inspect
from collections.abc import Callable
from typing import Any

from recommendation_core.pipeline import recommend_products
from schemas.recommend import NegativeFilters, RecommendFilters, RecommendResponse


class RecommendationTool:
    """Small wrapper around the recommendation chain."""

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
        """Call the recommendation chain and normalize the structured response."""
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
