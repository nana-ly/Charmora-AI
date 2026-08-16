"""统一的品类、关键词和品牌规则来源。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogTarget:
    canonical_key: str
    target_category: str
    catalog_category: str
    aliases: tuple[str, ...]
    keywords: tuple[str, ...]


_CATALOG_TARGETS: tuple[CatalogTarget, ...] = (
    CatalogTarget(
        canonical_key="phone",
        target_category="手机",
        catalog_category="数码电子",
        aliases=("手机",),
        keywords=("手机", "拍照", "剪视频", "续航", "游戏", "办公", "学生"),
    ),
    CatalogTarget(
        canonical_key="headphones",
        target_category="耳机",
        catalog_category="数码电子",
        aliases=("耳机",),
        keywords=("耳机", "降噪"),
    ),
    CatalogTarget(
        canonical_key="computer",
        target_category="电脑",
        catalog_category="数码电子",
        aliases=("电脑",),
        keywords=("电脑",),
    ),
    CatalogTarget(
        canonical_key="tablet",
        target_category="平板",
        catalog_category="数码电子",
        aliases=("平板",),
        keywords=("平板",),
    ),
    CatalogTarget(
        canonical_key="laptop",
        target_category="笔记本",
        catalog_category="数码电子",
        aliases=("笔记本",),
        keywords=("笔记本",),
    ),
    CatalogTarget(
        canonical_key="skin_care",
        target_category="护肤品",
        catalog_category="美妆护肤",
        aliases=("护肤产品", "护肤品", "化妆品", "防晒", "面霜", "护肤", "美妆"),
        keywords=(
            "护肤产品",
            "护肤品",
            "化妆品",
            "美妆",
            "精华",
            "敏感肌",
            "护肤",
            "抗初老",
            "面霜",
            "防晒",
            "保湿",
            "修护",
            "美白",
            "油皮",
            "干皮",
        ),
    ),
    CatalogTarget(
        canonical_key="food",
        target_category="食品",
        catalog_category="食品生活",
        aliases=(
            "方便食品",
            "调味品",
            "吃的",
            "食品",
            "零食",
            "茶饮",
            "牛奶",
            "酸奶",
        ),
        keywords=(
            "方便食品",
            "调味品",
            "吃的",
            "食品",
            "零食",
            "茶饮",
            "牛奶",
            "酸奶",
            "早餐",
        ),
    ),
    CatalogTarget(
        canonical_key="coffee",
        target_category="咖啡",
        catalog_category="食品生活",
        aliases=("咖啡",),
        keywords=("咖啡", "速溶", "新手", "拿铁", "冷萃", "低糖", "早餐", "办公室", "精品"),
    ),
    CatalogTarget(
        canonical_key="beverage",
        target_category="饮品",
        catalog_category="食品生活",
        aliases=("饮品",),
        keywords=("饮品",),
    ),
    CatalogTarget(
        canonical_key="t_shirt",
        target_category="T恤",
        catalog_category="服饰运动",
        aliases=("T恤",),
        keywords=("T恤", "通勤", "运动", "凉快", "速干", "夏天", "跑步", "健身", "防晒衣"),
    ),
    CatalogTarget(
        canonical_key="jacket",
        target_category="外套",
        catalog_category="服饰运动",
        aliases=("外套",),
        keywords=("外套",),
    ),
    CatalogTarget("accessories", "首饰发饰", "首饰发饰", ("首饰", "发饰", "项链", "耳钉", "抓夹", "手链", "戒指"), ("首饰", "发饰", "项链", "耳钉", "抓夹", "手链", "戒指", "通勤")),
    CatalogTarget("plush_charms", "挂件毛绒", "挂件毛绒", ("毛绒挂件", "毛绒", "挂件", "玩偶", "钥匙扣"), ("毛绒", "挂件", "玩偶", "钥匙扣", "可爱", "治愈")),
    CatalogTarget("bags_storage", "包袋收纳", "包袋收纳", ("化妆包", "斜挎包", "帆布袋", "卡包", "包包", "包袋"), ("化妆包", "斜挎包", "帆布袋", "卡包", "包包", "收纳", "通勤", "旅行")),
    CatalogTarget("beauty_tools", "美妆工具", "美妆工具", ("美妆工具", "化妆刷", "化妆镜", "睫毛夹", "气垫梳"), ("美妆工具", "化妆刷", "化妆镜", "睫毛夹", "气垫梳", "便携")),
    CatalogTarget("stationery", "文具", "文具", ("文具", "中性笔", "计划本", "笔袋", "便签", "荧光笔"), ("文具", "中性笔", "计划本", "笔袋", "便签", "荧光笔", "学习", "手账")),
    CatalogTarget("home_daily", "家居日用", "家居日用", ("宿舍收纳", "收纳用品", "日用品", "家居日用", "收纳盒", "脏衣篮", "水杯"), ("日用品", "家居", "收纳盒", "脏衣篮", "水杯", "宿舍", "桌面", "衣柜")),
    CatalogTarget("gift_sets", "礼赠组合", "礼赠组合", ("礼物组合", "礼赠", "送礼", "礼物"), ("礼物", "送朋友", "送同学", "生日", "开学", "惊喜", "组合")),
)

_CATALOG_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "数码电子": (
        "手机",
        "耳机",
        "电脑",
        "拍照",
        "剪视频",
        "平板",
        "笔记本",
        "续航",
        "游戏",
        "办公",
        "学生",
        "降噪",
    ),
    "美妆护肤": (
        "护肤产品",
        "护肤品",
        "化妆品",
        "美妆",
        "精华",
        "敏感肌",
        "护肤",
        "抗初老",
        "面霜",
        "防晒",
        "保湿",
        "修护",
        "美白",
        "油皮",
        "干皮",
    ),
    "服饰运动": (
        "T恤",
        "通勤",
        "运动",
        "凉快",
        "速干",
        "外套",
        "夏天",
        "跑步",
        "健身",
        "防晒衣",
    ),
    "食品生活": (
        "吃的",
        "食品",
        "零食",
        "茶饮",
        "牛奶",
        "酸奶",
        "方便食品",
        "调味品",
        "咖啡",
        "速溶",
        "饮品",
        "新手",
        "拿铁",
        "冷萃",
        "低糖",
        "早餐",
        "办公室",
        "精品",
    ),
    "首饰发饰": ("首饰", "发饰", "项链", "耳钉", "抓夹", "手链", "戒指"),
    "挂件毛绒": ("毛绒", "挂件", "玩偶", "钥匙扣", "可爱", "治愈"),
    "包袋收纳": ("化妆包", "斜挎包", "帆布袋", "卡包", "包包", "收纳", "旅行"),
    "美妆工具": ("美妆工具", "化妆刷", "化妆镜", "睫毛夹", "气垫梳"),
    "文具": ("文具", "中性笔", "计划本", "笔袋", "便签", "荧光笔", "手账"),
    "家居日用": ("日用品", "家居", "收纳盒", "脏衣篮", "水杯", "宿舍", "衣柜"),
    "礼赠组合": ("礼物", "送礼", "送朋友", "送同学", "生日", "开学", "惊喜", "组合"),
}

_BRAND_TERMS = (
    "Apple",
    "苹果",
    "小米",
    "华为",
    "荣耀",
    "OPPO",
    "vivo",
    "三星",
    "雅诗兰黛",
    "优衣库",
    "三顿半",
)


def catalog_targets() -> tuple[CatalogTarget, ...]:
    return _CATALOG_TARGETS


def target_category_aliases() -> tuple[tuple[str, str, str, str], ...]:
    aliases: list[tuple[str, str, str, str]] = []
    for target in _CATALOG_TARGETS:
        for alias in target.aliases:
            # 旧规则里部分 alias 的 display target 保持 alias 自身，如“防晒”“面霜”。
            display = alias if target.canonical_key == "skin_care" and alias not in {"护肤产品", "化妆品", "美妆"} else target.target_category
            if alias == "护肤产品":
                display = "护肤产品"
            aliases.append((alias, display, target.catalog_category, target.canonical_key))
    return tuple(sorted(aliases, key=lambda item: len(item[0]), reverse=True))


def category_keywords() -> dict[str, tuple[str, ...]]:
    return dict(_CATALOG_CATEGORY_KEYWORDS)


def keywords_for_catalog_category(category: str) -> tuple[str, ...]:
    return _CATALOG_CATEGORY_KEYWORDS.get(category, ())


def catalog_category_for_target(target_category: str) -> str | None:
    for _, canonical, catalog_category, _ in target_category_aliases():
        if canonical == target_category:
            return catalog_category
    return None


def canonical_key_for(
    target_category: str | None,
    catalog_category: str | None = None,
) -> str | None:
    if not target_category and not catalog_category:
        return None
    for _, canonical, _, key in target_category_aliases():
        if target_category == canonical:
            return key
    if target_category:
        for alias, _, _, key in target_category_aliases():
            if target_category == alias:
                return key
        for target in _CATALOG_TARGETS:
            if target_category == target.canonical_key:
                return target.canonical_key
    return None


def detect_catalog_category(query: str) -> str | None:
    # 先看明确目标 alias，再回落到宽泛关键词，避免“办公室喝的咖啡”被“办公”抢到数码类。
    for alias, _, catalog_category, _ in target_category_aliases():
        if alias in query:
            return catalog_category
    for category, keywords in _CATALOG_CATEGORY_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return category
    return None


def brand_terms() -> tuple[str, ...]:
    return _BRAND_TERMS
