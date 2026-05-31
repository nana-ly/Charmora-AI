import logging

from core.logging_config import configure_logging
from core.request_context import get_request_context, set_request_context


def test_configure_logging_sets_debug_level():
    configure_logging("DEBUG")

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_falls_back_to_info_for_invalid_level():
    configure_logging("NOT_A_LEVEL")

    assert logging.getLogger().level == logging.INFO


def test_configure_logging_does_not_duplicate_handlers():
    configure_logging("INFO")
    first_count = len(logging.getLogger().handlers)

    configure_logging("DEBUG")
    second_count = len(logging.getLogger().handlers)

    assert second_count == first_count


def test_configure_logging_uses_spaced_console_format():
    configure_logging("INFO")
    formatter = logging.getLogger().handlers[0].formatter
    record = logging.LogRecord(
        name="api.chat",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="chat request received",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert " | INFO  | api.chat | chat request received" in rendered


def test_logging_filter_adds_request_context_fields():
    configure_logging("INFO")
    formatter = logging.getLogger().handlers[0].formatter

    with set_request_context(
        request_id="req-test",
        session_id="session-test",
        turn_id="turn-test",
    ):
        record = logging.LogRecord(
            name="api.chat",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="chat request received",
            args=(),
            exc_info=None,
        )
        for handler in logging.getLogger().handlers:
            for log_filter in handler.filters:
                log_filter.filter(record)
        rendered = formatter.format(record)

    assert "request_id=req-test" in rendered
    assert "session_id=session-test" in rendered
    assert "turn_id=turn-test" in rendered


def test_request_context_resets_after_context_manager():
    with set_request_context(request_id="req-reset", session_id="session-reset"):
        assert get_request_context().request_id == "req-reset"

    assert get_request_context().request_id == "-"
