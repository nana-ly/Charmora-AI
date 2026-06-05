"""商品相关数据结构。"""

from pydantic import BaseModel, Field, model_validator


class ProductCard(BaseModel):
    """前端展示用商品卡片。

    字段保持与 Android 最小闭环稳定对齐，后续新增字段应优先通过可选字段扩展。
    """

    product_id: str
    title: str
    brand: str
    price: float
    price_range: str = ""
    reason: str
    evidence: str
    image_path: str | None = None
    image_url: str | None = None
    imageUrl: str | None = Field(default=None)
    rating: float = 0.0
    sold_count: int = 0
    review_count: int = 0
    marketing_desc: str = ""
    reviews: list[dict] = []
    faqs: list[dict] = []

    @model_validator(mode="after")
    def mirror_android_image_url(self):
        if self.imageUrl is None and self.image_url is not None:
            self.imageUrl = self.image_url
        if self.image_url is None and self.imageUrl is not None:
            self.image_url = self.imageUrl
        return self

