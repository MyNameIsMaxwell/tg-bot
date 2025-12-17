"""Pytest fixtures for configuring environment."""

import os

import pytest

from app import config


@pytest.fixture(scope="session", autouse=True)
def _test_env(tmp_path_factory) -> None:
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = tmp_dir / "test.db"

    os.environ.setdefault("TELEGRAM_API_ID", "100000")
    os.environ.setdefault("TELEGRAM_API_HASH", "hash")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:token")
    os.environ.setdefault("DEEPSEEK_API_KEY", "dummy")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    config.get_settings.cache_clear()



