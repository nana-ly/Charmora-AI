"""LLM 推荐理由服务。"""

from typing import Any, Protocol

from core.config import LLMConfig


class CompletionClient(Protocol):
    """文本补全客户端协议，便于测试时注入假客户端。"""

    def complete(self, prompt: str) -> str:
        """根据提示词返回生成文本。"""


class LLMReasonService:
    """可选的大模型推荐理由生成服务。

    当 LLM 未启用、密钥缺失或调用失败时，都会回退到模板理由，确保推荐接口稳定返回。
    """

    def __init__(
        self,
        config: LLMConfig,
        client: CompletionClient | None = None,
    ):
        self.config = config
        self.client = client

    def generate(
        self,
        query: str,
        product: dict[str, Any],
        evidence: str,
        fallback_reason: str | None = None,
    ) -> str:
        """生成推荐理由；不可调用 LLM 时返回模板兜底理由。"""
        fallback = fallback_reason or self._template_reason(query, product, evidence)
        if not self.config.is_available:
            return fallback

        try:
            client = self.client or self._create_client()
            reason = client.complete(self._build_prompt(query, product, evidence)).strip()
            return reason or fallback
        except Exception:
            # LLM 是增强能力，失败时不能影响推荐主链路。
            return fallback

    def _create_client(self) -> CompletionClient:
        """按需创建真实 LLM 客户端，避免未启用时加载外部依赖。"""
        from llm.client import OpenAIChatClient

        return OpenAIChatClient(self.config)

    def _build_prompt(
        self,
        query: str,
        product: dict[str, Any],
        evidence: str,
    ) -> str:
        """构造推荐理由提示词，控制输出简短且可解释。"""
        return (
            "请基于用户需求、商品信息和检索证据，生成一句中文推荐理由。\n"
            "要求：不要编造商品信息，不要超过 60 个中文字符。\n"
            f"用户需求：{query}\n"
            f"商品标题：{product.get('title', '')}\n"
            f"品牌：{product.get('brand', '')}\n"
            f"价格：{product.get('base_price', product.get('price', ''))}\n"
            f"证据：{evidence}"
        )

    def _template_reason(
        self,
        query: str,
        product: dict[str, Any],
        evidence: str,
    ) -> str:
        """生成稳定模板理由，作为 LLM 不可用时的降级结果。"""
        title = product.get("title", "这款商品")
        return f"{title} 与你的需求「{query}」匹配，{evidence}"

