"""旧检索路径兼容模块。

检索能力已经迁移到独立 retrieval 包。保留本模块是为了兼容可能仍在使用
recommendation_core.retrieval 的内部调用方。
"""

from retrieval.keyword import build_searchable_text, retrieve

__all__ = ["build_searchable_text", "retrieve"]
