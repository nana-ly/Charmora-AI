"""OpenAI 兼容聊天客户端。

为降低本地开发门槛，openai 包只在真实调用时延迟导入。
这保证默认未开启 LLM 的测试和接口不会因为缺少外部配置而失败。
"""

from dataclasses import dataclass
from typing import Any

from core.config import LLMConfig

OpenAI: Any | None = None


def _openai_client_class() -> Any:
    """延迟获取 OpenAI 客户端类，便于测试替换外部依赖。"""
    global OpenAI
    if OpenAI is None:
        from openai import OpenAI as ImportedOpenAI

        OpenAI = ImportedOpenAI
    return OpenAI


@dataclass(frozen=True)
class ChatInvokeResponse:
    """LangGraph 意图解析使用的最小响应结构。"""

    content: str


class OpenAIChatClient:
    """OpenAI 兼容接口的轻量封装。"""

    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, prompt: str) -> str:
        """调用聊天模型并返回文本结果。"""
        client = _openai_client_class()(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
        )
        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是电商导购助手，请给出简洁、可信的中文推荐理由。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=160,
        )

        message = response.choices[0].message.content
        return message.strip() if message else ""


class OpenAIInvokeChatClient:
    """提供 invoke 方法的 OpenAI 兼容聊天客户端。"""

    def __init__(self, config: LLMConfig):
        self.config = config

    def invoke(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 160,
    ) -> ChatInvokeResponse:
        """调用聊天模型并返回 LangGraph 兼容响应。"""
        client = _openai_client_class()(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
        )
        response = client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        message = response.choices[0].message.content
        return ChatInvokeResponse(content=message.strip() if message else "")


def create_llm(config: LLMConfig) -> OpenAIInvokeChatClient:
    """创建 Agent 意图解析使用的聊天模型适配器。"""
    return OpenAIInvokeChatClient(config)

