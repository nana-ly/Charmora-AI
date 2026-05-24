"""应用配置定义。

当前配置保持轻量：默认走本地关键词检索，LLM 只有在显式开启且提供密钥时才可用。
这样可以保证最小闭环离线可运行，同时为后续真实大模型接入预留稳定入口。
"""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMConfig:
    """大模型调用配置。

    enabled 只表示业务开关；is_available 会同时校验 API Key，避免误把未配置密钥的状态当成可调用。
    """

    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 8.0

    @property
    def is_available(self) -> bool:
        """判断当前配置是否满足真实调用大模型的最低条件。"""
        return self.enabled and bool(self.api_key.strip())


@dataclass(frozen=True)
class AppConfig:
    """后端应用级配置。

    retriever_mode 用来在关键词检索和未来向量检索之间切换；default_top_k 控制默认返回数量。
    """

    retriever_mode: str = "keyword"
    default_top_k: int = 3
    llm: LLMConfig = field(default_factory=LLMConfig)


def load_app_config(env_file: Path | None = Path(__file__).resolve().parents[1] / ".env") -> AppConfig:
    """从 .env 和环境变量加载配置，并提供适合本地开发的安全默认值。"""
    if env_file is not None:
        # 不覆盖已存在的环境变量，便于测试和部署平台显式传入配置。
        load_dotenv(env_file, override=False)

    return AppConfig(
        retriever_mode=os.getenv("RETRIEVER_MODE", "keyword"),
        default_top_k=int(os.getenv("DEFAULT_TOP_K", "3")),
        llm=LLMConfig(
            enabled=os.getenv("LLM_ENABLED", "false").lower() == "true",
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "8")),
        ),
    )
