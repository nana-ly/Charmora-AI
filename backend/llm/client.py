"""通用 LLM 客户端。自动适配 OpenAI 和 Anthropic 端点。"""

import json
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

from core.config import LLMConfig

OpenAI: Any | None = None


def _openai_client_class() -> Any:
    global OpenAI
    if OpenAI is None:
        from openai import OpenAI as ImportedOpenAI
        OpenAI = ImportedOpenAI
    return OpenAI


@dataclass(frozen=True)
class ChatInvokeResponse:
    content: str


class UniversalChatClient:
    """自动检测 OpenAI / Anthropic，统一调用。"""

    def __init__(self, config: LLMConfig):
        self.config = config

    # ── 公共接口 ──

    def complete(self, prompt: str) -> str:
        return self._call(
            system="你是电商导购助手，请给出简洁、可信的中文推荐理由。",
            user=prompt,
            temperature=0.2,
            max_tokens=160,
        )

    def invoke(self, messages: list[dict[str, str]], max_tokens: int = 160) -> ChatInvokeResponse:
        system, user = _split_system_user(messages)
        result = self._call(
            system=system or "你是电商导购 Agent。",
            user=user,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return ChatInvokeResponse(content=result)

    def generate_reply(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.8,
        max_tokens: int = 600,
    ) -> str:
        return self._call(
            system=system_prompt,
            user=user_content,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ── 核心调用 ──

    def _call(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        base = self.config.base_url.rstrip("/")
        if "anthropic" in base.lower():
            result = None
            try:
                result = self._via_anthropic(system, user, temperature, max_tokens, base)
            except Exception:
                pass
            if result and result.strip():
                return result
            # Anthropic 格式失败了，兜底走 OpenAI
            return self._via_openai(system, user, temperature, max_tokens)
        return self._via_openai(system, user, temperature, max_tokens)

    # ── OpenAI ──

    def _via_openai(
        self, system: str, user: str, temperature: float, max_tokens: int
    ) -> str:
        client = _openai_client_class()(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
        )
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        msg = resp.choices[0].message.content
        return msg.strip() if msg else ""

    # ── Anthropic ──

    def _via_anthropic(
        self, system: str, user: str, temperature: float, max_tokens: int, base_url: str
    ) -> str:
        url = f"{base_url}/messages"
        payload = json.dumps({
            "model": self.config.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urlrequest.Request(url, data=payload, method="POST")
        req.add_header("x-api-key", self.config.api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("Content-Type", "application/json")

        try:
            with urlrequest.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                text = data.get("content", [{}])[0].get("text", "")
                if not text:
                    # 尝试 OpenAI 格式兼容（有些 anthropic 代理用 OpenAI 格式）
                    text = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                return text
        except URLError as e:
            body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            raise RuntimeError(f"Anthropic request failed: {e}\n{body[:300]}")


def _split_system_user(messages: list[dict[str, str]]) -> tuple[str | None, str]:
    system = None
    user_parts = []
    for m in messages:
        if m.get("role") == "system":
            system = m.get("content", "")
        else:
            user_parts.append(f"[{m.get('role', '')}]: {m.get('content', '')}")
    if system is None and len(user_parts) == 1:
        # 单独的 user message 直接当 user prompt
        return None, user_parts[0]
    return system, "\n".join(user_parts)


def create_llm(config: LLMConfig) -> UniversalChatClient:
    return UniversalChatClient(config)
