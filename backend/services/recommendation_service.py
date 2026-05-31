"""API 路由和 Agent 工具共用的推荐应用服务。"""

from __future__ import annotations

import threading
from typing import Any, Callable

from core.config import AppConfig, load_app_config
from recommendation_core.pipeline import (
    create_default_reason_service,
    recommend_products,
)
from recommendation_core.reason import ReasonService
from retrieval.base import Retriever
from schemas.recommend import NegativeFilters
from services.retriever_factory import select_retriever

RetrieverFactory = Callable[[AppConfig], Retriever]
ReasonServiceFactory = Callable[[], ReasonService]
RecommendFunc = Callable[..., dict[str, Any]]


class RecommendationService:
    """应用级推荐服务，缓存配置、retriever 和 reason service。

    缓存边界是当前 Python 进程内的 service 实例；多进程、多 worker 或多实例部署不会共享。
    RLock 只保护首次懒初始化，后续检索调用假设 retriever.search() 和 reason_service.generate()
    是可并发读的。如果底层客户端不满足该假设，应在对应适配器中增加更细粒度的保护。
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        retriever_factory: RetrieverFactory | None = None,
        reason_service_factory: ReasonServiceFactory | None = None,
        recommend_func: RecommendFunc | None = None,
    ) -> None:
        self.config = config or load_app_config()
        self._retriever_factory = retriever_factory or select_retriever
        self._reason_service_factory = (
            reason_service_factory or create_default_reason_service
        )
        self._recommend_func = recommend_func or recommend_products
        self._lock = threading.RLock()
        self._retriever: Retriever | None = None
        self._reason_service: ReasonService | None = None

    def _get_retriever(self) -> Retriever:
        if self._retriever is None:
            with self._lock:
                if self._retriever is None:
                    self._retriever = self._retriever_factory(self.config)
        return self._retriever

    def _get_reason_service(self) -> ReasonService:
        if self._reason_service is None:
            with self._lock:
                if self._reason_service is None:
                    self._reason_service = self._reason_service_factory()
        return self._reason_service

    def recommend(
        self,
        query: str,
        top_k: int | None = None,
        negative_filters: NegativeFilters | None = None,
    ) -> dict[str, Any]:
        """使用缓存的 retriever/reason service 执行推荐链路。"""
        kwargs: dict[str, Any] = {
            "top_k": top_k if top_k is not None else self.config.default_top_k,
            "retriever": self._get_retriever(),
            "reason_service": self._get_reason_service(),
        }
        if negative_filters is not None:
            kwargs["negative_filters"] = negative_filters
        return self._recommend_func(query, **kwargs)

    def ready(self) -> dict[str, Any]:
        """检查推荐依赖是否可用，失败时不吞错，转成 readiness 响应字段。"""
        try:
            self._get_retriever()
        except Exception as exc:
            return {
                "status": "not_ready",
                "retriever_mode": self.config.retriever_mode,
                "error": str(exc),
            }
        return {
            "status": "ready",
            "retriever_mode": self.config.retriever_mode,
        }


_service_lock = threading.RLock()
_recommendation_service: RecommendationService | None = None


def get_recommendation_service() -> RecommendationService:
    """返回进程内全局推荐服务，供兼容函数和 API 依赖复用。"""
    global _recommendation_service
    if _recommendation_service is None:
        with _service_lock:
            if _recommendation_service is None:
                _recommendation_service = RecommendationService()
    return _recommendation_service


def reset_recommendation_service_for_tests() -> None:
    """重置全局推荐服务，避免测试之间共享缓存状态。"""
    global _recommendation_service
    with _service_lock:
        _recommendation_service = None


def run_recommendation(
    query: str,
    top_k: int | None = None,
    negative_filters: NegativeFilters | None = None,
) -> dict[str, Any]:
    """兼容旧入口：委托给进程内全局 RecommendationService。"""
    return get_recommendation_service().recommend(
        query,
        top_k=top_k,
        negative_filters=negative_filters,
    )
