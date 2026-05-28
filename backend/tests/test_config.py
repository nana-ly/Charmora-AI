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
