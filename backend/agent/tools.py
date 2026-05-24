"""Agent 可调用工具。"""

from recommendation_core.pipeline import recommend_products
from schemas.recommend import RecommendFilters, RecommendResponse


class RecommendationTool:
    """推荐工具封装。

    Agent 只关心工具输入输出，不直接依赖推荐链路内部模块，方便后续增加搜索、比价等工具。
    """

    def run(self, query: str, top_k: int = 3) -> RecommendResponse:
        """调用推荐链路并转换成结构化响应对象。"""
        result = recommend_products(query, top_k=top_k)
        return RecommendResponse(
            query=result["query"],
            filters=RecommendFilters(**result["filters"]),
            items=result["items"],
        )

