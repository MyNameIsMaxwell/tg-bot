"""Tests for Telegram client helpers."""

from types import SimpleNamespace

from app import telegram_client


def test_relevant_message_text():
    msg = SimpleNamespace(action=None, message="Hello")
    assert telegram_client._is_relevant_message(msg)  # pylint: disable=protected-access


def test_irrelevant_service_message():
    msg = SimpleNamespace(action="service", message="User joined")
    assert not telegram_client._is_relevant_message(
        msg
    )  # pylint: disable=protected-access


def test_irrelevant_empty_text():
    msg = SimpleNamespace(action=None, message="   ")
    assert not telegram_client._is_relevant_message(
        msg
    )  # pylint: disable=protected-access



