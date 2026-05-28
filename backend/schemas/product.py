"""商品相关数据结构。"""

from pydantic import BaseModel


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

