"""商品数据加载模块。

当前使用仓库内的本地 JSON 数据集，后续如果接入数据库或商品服务，只需要替换这里的加载逻辑，
推荐链路上层仍然可以使用同样的商品字典结构。
"""

import json
from pathlib import Path
from typing import Any


DATASET_DIR = Path(__file__).resolve().parents[2] / "ecommerce_agent_dataset"


def load_products(dataset_dir: Path = DATASET_DIR) -> list[dict[str, Any]]:
    """从本地数据集加载商品 JSON，作为推荐流程的默认商品来源。"""
    loaded_products: list[dict[str, Any]] = []

    for product_file in sorted(dataset_dir.glob("*/data/*.json")):
        with product_file.open("r", encoding="utf-8") as file:
            loaded_products.append(json.load(file))

    return loaded_products


# 模块级缓存用于本地最小闭环，避免每次推荐请求都重复读取 JSON 文件。
products = load_products()

