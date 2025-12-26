"""Pytest fixtures for configuring environment."""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app import config


@pytest.fixture(scope="session", autouse=True)
def _test_env(tmp_path_factory) -> None:
    """Set up test environment variables."""
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = tmp_dir / "test.db"

    os.environ.setdefault("TELEGRAM_API_ID", "100000")
    os.environ.setdefault("TELEGRAM_API_HASH", "hash")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:token")
    os.environ.setdefault("DEEPSEEK_API_KEY", "dummy")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    os.environ.setdefault("WEBAPP_BASE_URL", "http://localhost:8000")

    config.get_settings.cache_clear()


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Initialize test database."""
    from app.db import init_db
    await init_db()


@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing FastAPI endpoints."""
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_deepseek_response():
    """Mock successful DeepSeek API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "📌 Тестовая сводка новостей https://t.me/test/1\n• Второй пункт https://t.me/test/2"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }


@pytest.fixture
def mock_telegram_init_data():
    """Generate valid Telegram initData for testing."""
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode
    
    def _generate(user_id: int = 12345, username: str = "testuser") -> str:
        bot_token = "123:token"
        payload = {
            "auth_date": str(int(time.time())),
            "user": json.dumps({"id": user_id, "username": username}),
        }
        # Calculate hash
        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(payload.items())
        )
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()
        hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        payload["hash"] = hash_value
        return urlencode(payload)
    
    return _generate



