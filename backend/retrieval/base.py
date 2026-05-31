"""检索层基础协议与结果结构。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalResult:
    """检索结果。

    product 保存原始商品字典；evidence 用于解释召回依据；score 方便后续调试排序。
    trace 字段均有默认值，保证旧测试和轻量 fake retriever 可继续只填核心字段。
    """

    product: dict[str, Any]
    evidence: str
    score: float = 0.0
    rank: int | None = None
    source: str | None = None
    retriever_mode: str | None = None
    score_type: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


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

