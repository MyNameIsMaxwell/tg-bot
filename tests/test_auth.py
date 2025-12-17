"""Tests for Telegram initData validation."""

import json
import time
from urllib.parse import urlencode

import pytest

from app import auth
from app.db import SessionLocal, init_db


def _build_init_data(monkeypatch, user_id: int = 1, username: str = "tester") -> str:
    monkeypatch.setattr(auth.settings, "telegram_bot_token", "123:token", raising=False)
    payload = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id, "username": username}),
    }
    hash_value = auth._calculate_hash({**payload})  # pylint: disable=protected-access
    payload["hash"] = hash_value
    return urlencode(payload)


@pytest.mark.asyncio
async def test_authenticate_user_success(monkeypatch):
    await init_db()
    init_data = _build_init_data(monkeypatch)
    async with SessionLocal() as session:
        user = await auth.authenticate_user(init_data, session)
        assert user.telegram_user_id == 1
        assert user.username == "tester"


@pytest.mark.asyncio
async def test_authenticate_user_invalid_hash(monkeypatch):
    await init_db()
    init_data = _build_init_data(monkeypatch) + "corruption"
    async with SessionLocal() as session:
        with pytest.raises(auth.InitDataError):
            await auth.authenticate_user(init_data, session)



