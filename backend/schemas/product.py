"""商品相关数据结构。"""

from pydantic import BaseModel, Field


class ProductCard(BaseModel):
    """前端展示用商品卡片。

    字段保持与 Android 最小闭环稳定对齐，后续新增字段应优先通过可选字段扩展。
    """

    product_id: str
    title: str
    brand: str
    price: float
    reason: str
    evidence: str


class RetrievedProduct(BaseModel):
    """检索层返回的商品候选项。

    score 表示召回或排序分数，metadata 保留给向量库、标签和库存等扩展信息。
    """

    product: dict
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)
