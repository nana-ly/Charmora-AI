"""大模型接入层。

本包只负责和 LLM 服务交互或生成 LLM 提示词，不直接编排推荐流程。
推荐链路通过 ReasonService 接口注入，确保没有密钥时仍能离线运行。
"""

from llm.client import OpenAIChatClient
from llm.reason_service import LLMReasonService

__all__ = ["LLMReasonService", "OpenAIChatClient"]

