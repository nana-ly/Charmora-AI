from core.config import load_app_config


def test_log_level_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    config = load_app_config(env_file=None)

    assert config.log_level == "INFO"


def test_log_level_reads_environment_value(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")

    config = load_app_config(env_file=None)

    assert config.log_level == "DEBUG"


def test_default_top_k_reads_environment_value(monkeypatch):
    monkeypatch.setenv("DEFAULT_TOP_K", "5")

    config = load_app_config(env_file=None)

    assert config.default_top_k == 5


def test_load_app_config_reads_conversation_store_settings(monkeypatch):
    monkeypatch.setenv("CONVERSATION_STORE_MODE", "sqlite")
    monkeypatch.setenv(
        "CONVERSATION_STORE_PATH",
        "data/test-conversations.sqlite3",
    )

    config = load_app_config(env_file=None)

    assert config.conversation_store_mode == "sqlite"
    assert config.conversation_store_path == "data/test-conversations.sqlite3"


def test_load_app_config_reads_conversation_store_update_retries(monkeypatch):
    monkeypatch.setenv("CONVERSATION_STORE_UPDATE_RETRIES", "5")

    config = load_app_config(env_file=None)

    assert config.conversation_store_update_retries == 5


def test_load_app_config_reads_product_image_settings(monkeypatch):
    monkeypatch.setenv("PRODUCT_IMAGE_BASE_URL", "https://cdn.example.com/products")
    monkeypatch.setenv("PRODUCT_IMAGE_STATIC_ROOT", "../dataset")
    monkeypatch.setenv("PRODUCT_IMAGE_STATIC_ENABLED", "false")

    config = load_app_config(env_file=None)

    assert config.product_image_base_url == "https://cdn.example.com/products"
    assert config.product_image_static_root == "../dataset"
    assert config.product_image_static_enabled is False
