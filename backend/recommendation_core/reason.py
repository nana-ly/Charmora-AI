"""推荐理由生成模块。"""

from typing import Any


def generate_reason(query: str, product: dict[str, Any], evidence: str) -> str:
    """用模板生成中文推荐理由，先保证演示链路稳定。"""
    title = product.get("title", "这款商品")
    return f"{title} 与你的需求「{query}」匹配，{evidence}"

