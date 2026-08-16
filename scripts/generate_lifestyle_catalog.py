"""Generate the deterministic ShopGuide Lifestyle demo catalog."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ecommerce_agent_dataset" / "synthetic_lifestyle_v1" / "products.json"

CATEGORIES = {
    "首饰发饰": [
        ("奶油白蝴蝶结抓夹", 19.9, "甜美日常盘发", "奶油白"),
        ("星月叠戴项链", 29.9, "简约通勤搭配", "银色"),
        ("磨砂几何发圈三件套", 15.9, "低饱和日常发饰", "燕麦色"),
        ("珍珠小花耳钉", 22.9, "轻巧礼赠首饰", "珍珠白"),
        ("复古方糖戒指", 26.9, "可调节叠戴戒指", "金色"),
        ("彩色串珠手链", 18.9, "活泼夏日配饰", "彩色"),
    ],
    "挂件毛绒": [
        ("困困小熊毛绒挂件", 25.9, "书包钥匙治愈挂件", "焦糖棕"),
        ("软糖兔坐姿玩偶", 49.9, "宿舍床头软萌玩偶", "草莓粉"),
        ("吐司小狗钥匙扣", 19.9, "轻量可爱随身挂件", "奶油黄"),
        ("云朵猫咪毛绒挂件", 23.9, "送朋友的小巧礼物", "雾蓝"),
        ("趴趴企鹅桌面玩偶", 39.9, "桌面陪伴毛绒摆件", "黑白"),
        ("迷你恐龙挂件", 21.9, "双肩包趣味挂饰", "抹茶绿"),
    ],
    "包袋收纳": [
        ("云朵绗缝化妆包", 35.9, "旅行通勤分区收纳", "雾紫"),
        ("轻便多隔层斜挎包", 69.9, "轻装通勤随身包", "黑色"),
        ("透明网纱洗漱包", 29.9, "浴室旅行可视收纳", "透明白"),
        ("小熊刺绣帆布袋", 45.9, "上课通勤大容量包", "米白"),
        ("抽绳束口便当袋", 24.9, "午餐与小物手提袋", "格纹绿"),
        ("三层证件卡包", 18.9, "校园门禁卡收纳", "奶茶色"),
    ],
    "美妆工具": [
        ("便携气垫梳", 16.9, "通勤旅行随身梳", "樱花粉"),
        ("旅行化妆刷五件套", 39.9, "新手便携基础刷具", "香槟色"),
        ("软硅胶洁面刷", 12.9, "日常清洁辅助工具", "薄荷绿"),
        ("迷你睫毛夹", 15.9, "化妆包便携工具", "银色"),
        ("双面折叠化妆镜", 22.9, "桌面随身两用镜", "奶油白"),
        ("吸水干发帽", 19.9, "洗护日常速干用品", "浅紫"),
    ],
    "文具": [
        ("奶油色按动中性笔六支装", 15.9, "课堂笔记办公记录", "奶油色"),
        ("周计划线圈本", 18.9, "学习工作周计划", "鼠尾草绿"),
        ("透明磨砂笔袋", 16.9, "大容量文具收纳", "半透明"),
        ("猫咪索引便签套装", 12.9, "阅读标记手账装饰", "彩色"),
        ("桌面迷你订书机", 14.9, "宿舍办公桌工具", "浅蓝"),
        ("柔和色双头荧光笔五支装", 17.9, "重点标记手账配色", "柔和彩色"),
    ],
    "家居日用": [
        ("桌面分格收纳盒", 24.9, "宿舍办公桌小物收纳", "半透明"),
        ("旅行衣物收纳袋三件套", 45.9, "旅行箱衣柜分类整理", "燕麦米"),
        ("按压式桌面垃圾桶", 29.9, "桌面化妆台小型垃圾桶", "奶油白"),
        ("可折叠脏衣篮", 39.9, "宿舍浴室衣物收纳", "浅灰"),
        ("便携随行水杯", 32.9, "学习通勤日常饮水", "雾蓝"),
        ("香氛衣柜挂片三片装", 19.9, "衣柜抽屉清新用品", "白茶"),
    ],
    "礼赠组合": [
        ("元气学习礼物组合", 49.9, "同学朋友开学礼物", "清新绿"),
        ("治愈系随身礼物组合", 59.9, "毛绒挂件化妆包组合", "甜心粉"),
        ("通勤新手实用组合", 89.9, "斜挎包卡包随身梳", "黑色"),
        ("宿舍收纳入门组合", 79.9, "桌面与衣物收纳组合", "燕麦米"),
        ("手账文具惊喜组合", 39.9, "计划本笔和便签组合", "柔和彩色"),
        ("周末旅行轻装组合", 99.9, "洗漱包收纳袋干发帽", "雾紫"),
    ],
}


def build_catalog() -> list[dict]:
    products: list[dict] = []
    for category_index, (category, specs) in enumerate(CATEGORIES.items(), start=1):
        for item_index, (title, price, description, color) in enumerate(specs, start=1):
            product_id = f"life-{category_index:02d}-{item_index:03d}"
            products.append(
                {
                    "product_id": product_id,
                    "title": title,
                    "brand": "ShopGuide Select",
                    "category": category,
                    "base_price": price,
                    "image_path": f"synthetic_lifestyle_v1/images/category-{category_index:02d}.jpg",
                    "attributes": {
                        "color": color,
                        "data_origin": "synthetic",
                        "source_batch": "synthetic-lifestyle-v1",
                        "image_source": "Wikimedia Commons category reference",
                    },
                    "skus": [
                        {
                            "sku_id": f"{product_id}-default",
                            "properties": {"颜色": color, "规格": "默认规格"},
                            "price": price,
                            "stock": 18 + ((category_index * 11 + item_index * 7) % 57),
                        }
                    ],
                    "rag_knowledge": {
                        "marketing_description": f"{description}。模拟商品，仅用于 ShopGuide 功能演示。"
                    },
                }
            )
    return products


def main() -> None:
    catalog = build_catalog()
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated={len(catalog)} output={OUTPUT}")


if __name__ == "__main__":
    main()
