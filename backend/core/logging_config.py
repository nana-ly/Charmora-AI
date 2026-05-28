"""控制台日志配置。"""

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(log_level: str) -> None:
    """配置标准库控制台日志，避免重复添加处理器。"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        return

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
