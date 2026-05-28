import logging

from core.logging_config import configure_logging


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
