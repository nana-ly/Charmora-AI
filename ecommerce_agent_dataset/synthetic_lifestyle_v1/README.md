# Synthetic Lifestyle Catalog v1

这是 ShopGuide Lifestyle 的第一批纯模拟商品数据，与原始电商样例分目录保存，不代表真实品牌、库存或售价。

- 数据来源标识：`synthetic-lifestyle-v1`
- 建议导入来源名称：`生活杂货模拟数据 v1`
- 商品文件：`products.json`
- 当前范围：首饰发饰、挂件毛绒、包袋收纳、美妆工具、文具、家居日用、礼赠组合
- 当前数量：42 个商品（每类 6 个），可由 `scripts/generate_lifestyle_catalog.py` 确定性重建

通过导入 API 使用时，应显式传入：

```text
source_key=synthetic-lifestyle-v1
source_name=生活杂货模拟数据 v1
default_inventory=0
```

图片保存在本目录的 `images` 子目录。v1 每个品类共用一张参考图，图片来源与许可记录在 `images/ATTRIBUTION.md`；后续可逐商品替换，不影响商品事实字段和导入 ID。
