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
class DatabaseConfig:
    """PostgreSQL business database configuration."""

    url: str = "postgresql+psycopg://shopguide:shopguide@localhost:5432/shopguide"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout_seconds: float = 10.0
    echo: bool = False
    expected_revision: str = "20260816_0002"


@dataclass(frozen=True)
class MultimodalConfig:
    upload_root: str = "data/uploads"
    max_image_bytes: int = 10 * 1024 * 1024
    max_audio_bytes: int = 15 * 1024 * 1024
    max_audio_seconds: int = 60
    image_embedding_url: str = ""
    image_embedding_api_key: str = ""
    vision_enabled: bool = False
    vision_api_key: str = ""
    vision_base_url: str = "https://api.openai.com/v1"
    vision_model: str = "gpt-4o-mini"
    asr_enabled: bool = False
    asr_api_key: str = ""
    asr_base_url: str = "https://api.openai.com/v1"
    asr_model: str = "whisper-1"
    tts_enabled: bool = False
    tts_api_key: str = ""
    tts_base_url: str = "https://api.openai.com/v1"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"


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
    catalog_source: str = "legacy"
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    multimodal: MultimodalConfig = field(default_factory=MultimodalConfig)


def load_app_config(env_file: Path | None = Path(__file__).resolve().parents[1] / ".env") -> AppConfig:
    """从 .env 和环境变量加载配置，并提供适合本地开发的安全默认值。"""
    if env_file is not None:
        # 不覆盖已存在的环境变量，便于测试和部署平台显式传入配置。
        load_dotenv(env_file, override=False)

    demo_database = Path(__file__).resolve().parents[1] / "data" / "charmora_demo.db"
    demo_database.parent.mkdir(parents=True, exist_ok=True)
    demo_database_url = "sqlite+pysqlite:///" + demo_database.as_posix()

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
        catalog_source=os.getenv(
            "CATALOG_SOURCE",
            "postgresql" if os.getenv("DATABASE_URL") else "legacy",
        ),
        database=DatabaseConfig(
            url=os.getenv(
                "DATABASE_URL",
                demo_database_url,
            ),
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
            pool_timeout_seconds=float(os.getenv("DATABASE_POOL_TIMEOUT_SECONDS", "10")),
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            expected_revision=os.getenv("DATABASE_EXPECTED_REVISION", "20260816_0002"),
        ),
        multimodal=MultimodalConfig(
            upload_root=os.getenv("MULTIMODAL_UPLOAD_ROOT", "data/uploads"),
            max_image_bytes=int(os.getenv("MAX_IMAGE_UPLOAD_BYTES", str(10 * 1024 * 1024))),
            max_audio_bytes=int(os.getenv("MAX_AUDIO_UPLOAD_BYTES", str(15 * 1024 * 1024))),
            max_audio_seconds=int(os.getenv("MAX_AUDIO_SECONDS", "60")),
            image_embedding_url=os.getenv("IMAGE_EMBEDDING_URL", ""),
            image_embedding_api_key=os.getenv("IMAGE_EMBEDDING_API_KEY", ""),
            vision_enabled=os.getenv("VISION_ENABLED", "false").lower() == "true",
            vision_api_key=os.getenv("VISION_API_KEY", ""),
            vision_base_url=os.getenv("VISION_BASE_URL", "https://api.openai.com/v1"),
            vision_model=os.getenv("VISION_MODEL", "gpt-4o-mini"),
            asr_enabled=os.getenv("ASR_ENABLED", "false").lower() == "true",
            asr_api_key=os.getenv("ASR_API_KEY", ""),
            asr_base_url=os.getenv("ASR_BASE_URL", "https://api.openai.com/v1"),
            asr_model=os.getenv("ASR_MODEL", "whisper-1"),
            tts_enabled=os.getenv("TTS_ENABLED", "false").lower() == "true",
            tts_api_key=os.getenv("TTS_API_KEY", ""),
            tts_base_url=os.getenv("TTS_BASE_URL", "https://api.openai.com/v1"),
            tts_model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.getenv("TTS_VOICE", "alloy"),
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
