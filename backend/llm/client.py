"""OpenAI 兼容聊天客户端。

为降低本地开发门槛，openai 包只在真实调用时延迟导入。
这保证默认未开启 LLM 的测试和接口不会因为缺少外部配置而失败。
"""

from core.config import LLMConfig


class OpenAIChatClient:
    """OpenAI 兼容接口的轻量封装。"""

    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, prompt: str) -> str:
        """调用聊天模型并返回文本结果。"""
        from openai import OpenAI

        client = OpenAI(
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

