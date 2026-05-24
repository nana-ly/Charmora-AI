"""检索层基础协议与结果结构。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalResult:
    """检索结果。

    product 保存原始商品字典；evidence 用于解释召回依据；score 方便后续调试排序。
    """

    product: dict[str, Any]
    evidence: str
    score: float = 0.0

    def to_legacy_item(self) -> dict[str, Any]:
        """转换成旧推荐链路使用的字典结构，保持接口兼容。"""
        return {
            "product": self.product,
            "evidence": self.evidence,
        }


class Retriever(ABC):
    """检索器抽象基类。"""

    @abstractmethod
    def search(
        self,
        query: str,
        candidates: list[dict[str, Any]] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """根据用户需求从候选商品中召回 Top K 结果。"""

