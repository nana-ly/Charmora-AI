"""推荐理由生成模块。"""

from typing import Any, Protocol


class ReasonService(Protocol):
    """推荐理由服务协议，支持模板服务或 LLM 服务注入。"""

    def generate(
        self,
        query: str,
        product: dict[str, Any],
        evidence: str,
        fallback_reason: str | None = None,
    ) -> str:
        """生成推荐理由。"""


def template_reason(query: str, product: dict[str, Any], evidence: str) -> str:
    """用模板生成中文推荐理由，先保证演示链路稳定。"""
    title = product.get("title", "这款商品")
    return f"{title} 与你的需求「{query}」匹配，{evidence}"


def generate_reason(
    query: str,
    product: dict[str, Any],
    evidence: str,
    reason_service: ReasonService | None = None,
) -> str:
    """生成推荐理由；可选注入 LLM 服务，默认使用模板。"""
    fallback = template_reason(query, product, evidence)
    if reason_service is None:
        return fallback

    return reason_service.generate(
        query=query,
        product=product,
        evidence=evidence,
        fallback_reason=fallback,
    )
