"""控制台日志配置。"""

import logging

from core.request_context import get_request_context


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s "
    "| request_id=%(request_id)s session_id=%(session_id)s turn_id=%(turn_id)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_BASE_LOG_RECORD_FACTORY = logging.getLogRecordFactory()
_REQUEST_CONTEXT_FACTORY_INSTALLED = False


class RequestContextFilter(logging.Filter):
    """给所有日志记录补齐请求上下文字段，避免 formatter 缺字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_request_context()
        record.request_id = getattr(record, "request_id", context.request_id)
        record.session_id = getattr(record, "session_id", context.session_id)
        record.turn_id = getattr(record, "turn_id", context.turn_id)
        return True


class RequestContextFormatter(logging.Formatter):
    """即使绕过 handler filter 直接格式化，也能补齐上下文字段。"""

    def format(self, record: logging.LogRecord) -> str:
        RequestContextFilter().filter(record)
        return super().format(record)


def _install_request_context_record_factory() -> None:
    """在 LogRecord 创建阶段注入上下文，兼容 pytest caplog 等后加 handler。"""
    global _REQUEST_CONTEXT_FACTORY_INSTALLED
    if _REQUEST_CONTEXT_FACTORY_INSTALLED:
        return

    def record_factory(*args, **kwargs):
        record = _BASE_LOG_RECORD_FACTORY(*args, **kwargs)
        RequestContextFilter().filter(record)
        return record

    logging.setLogRecordFactory(record_factory)
    _REQUEST_CONTEXT_FACTORY_INSTALLED = True


def configure_logging(log_level: str) -> None:
    """配置标准库控制台日志，避免重复添加处理器。"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    _install_request_context_record_factory()

    formatter = RequestContextFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    context_filter = RequestContextFilter()
    if not any(
        isinstance(log_filter, RequestContextFilter)
        for log_filter in root_logger.filters
    ):
        root_logger.addFilter(context_filter)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)
        root_logger.addHandler(handler)
        return

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        if not any(
            isinstance(log_filter, RequestContextFilter)
            for log_filter in handler.filters
        ):
            handler.addFilter(context_filter)
