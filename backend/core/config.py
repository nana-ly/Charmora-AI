"""应用配置定义。

当前配置默认走 RAG 向量检索；如果向量检索不可用，应暴露错误而不是静默切换检索路径。
LLM 只有在显式开启且提供密钥时才可用。
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
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3/"
    model: str = "p-20260514111645-lmgt2"
    timeout_seconds: float = 8.0

    @property
    def is_available(self) -> bool:
        """判断当前配置是否满足真实调用大模型的最低条件。"""
        return self.enabled and bool(self.api_key.strip())


@dataclass(frozen=True)
class RAGConfig:
    """商品 RAG 检索配置。"""

    embedding_url: str = ""
    embedding_api: str = ""
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024


@dataclass(frozen=True)
class AppConfig:
    """后端应用级配置。

    agent_runner 控制 /chat 使用规则版 Runner 还是 LangGraph Runner；
    retriever_mode 用来在关键词检索和向量检索之间切换；default_top_k 控制默认返回数量。
    """

    agent_runner: str = "langgraph"
    retriever_mode: str = "vector"
    default_top_k: int = 3
    log_level: str = "INFO"
    conversation_store_mode: str = "memory"
    conversation_store_path: str = "data/conversations.sqlite3"
    agent_session_lock_enabled: bool = True
    conversation_store_update_retries: int = 3
    recommend_trace_enabled: bool = False
    product_image_base_url: str = "/assets/products"
    product_image_static_root: str = "../ecommerce_agent_dataset"
    product_image_static_enabled: bool = True
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)


def load_app_config(env_file: Path | None = Path(__file__).resolve().parents[1] / ".env") -> AppConfig:
    """从 .env 和环境变量加载配置，并提供适合本地开发的安全默认值。"""
    if env_file is not None:
        # 不覆盖已存在的环境变量，便于测试和部署平台显式传入配置。
        load_dotenv(env_file, override=False)

    return AppConfig(
        agent_runner=os.getenv("AGENT_RUNNER", "langgraph"),
        retriever_mode=os.getenv("RETRIEVER_MODE", "vector"),
        default_top_k=int(os.getenv("DEFAULT_TOP_K", "3")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        conversation_store_mode=os.getenv("CONVERSATION_STORE_MODE", "memory"),
        conversation_store_path=os.getenv(
            "CONVERSATION_STORE_PATH",
            "data/conversations.sqlite3",
        ),
        agent_session_lock_enabled=(
            os.getenv("AGENT_SESSION_LOCK_ENABLED", "true").lower() == "true"
        ),
        conversation_store_update_retries=int(
            os.getenv("CONVERSATION_STORE_UPDATE_RETRIES", "3")
        ),
        recommend_trace_enabled=(
            os.getenv("RECOMMEND_TRACE_ENABLED", "false").lower() == "true"
        ),
        product_image_base_url=os.getenv(
            "PRODUCT_IMAGE_BASE_URL",
            "/assets/products",
        ),
        product_image_static_root=os.getenv(
            "PRODUCT_IMAGE_STATIC_ROOT",
            "../ecommerce_agent_dataset",
        ),
        product_image_static_enabled=(
            os.getenv("PRODUCT_IMAGE_STATIC_ENABLED", "true").lower() == "true"
        ),
        llm=LLMConfig(
            enabled=os.getenv("LLM_ENABLED", "false").lower() == "true",
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "8")),
        ),
        rag=RAGConfig(
            embedding_url=os.getenv("embedding_url", ""),
            embedding_api=os.getenv("embedding_api", ""),
            embedding_model=os.getenv("embedding_model", "text-embedding-v4"),
            embedding_dimensions=_read_embedding_dimensions(),
        ),
    )


def _read_embedding_dimensions() -> int:
    """读取 embedding 维度，兼容早期文档中的拼写。"""
    value = (
        os.getenv("embedding_dimensions")
        or os.getenv("dimention")
        or os.getenv("dimentions")
        or "1024"
    )
    return int(value)
