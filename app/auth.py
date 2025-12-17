"""Telegram WebApp initData validation and FastAPI dependency."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Annotated, Dict, Optional
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_session
from .models import User


settings = get_settings()


class InitDataError(HTTPException):
    """Custom HTTP exception for invalid init data."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _parse_init_data(raw_init_data: str) -> Dict[str, str]:
    if not raw_init_data:
        raise InitDataError("Missing initData")
    parsed = dict(parse_qsl(raw_init_data, keep_blank_values=True))
    if "hash" not in parsed:
        raise InitDataError("Missing hash in initData")
    return parsed


def _calculate_hash(data: Dict[str, str]) -> str:
    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items())
        if key != "hash"
    )
    secret_key = hmac.new(
        b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256
    ).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def _validate_auth_date(auth_date_str: Optional[str]) -> None:
    if not auth_date_str:
        raise InitDataError("auth_date not found")
    try:
        auth_date = datetime.fromtimestamp(int(auth_date_str), tz=timezone.utc)
    except (TypeError, ValueError):
        raise InitDataError("Invalid auth_date") from None
    now = datetime.now(tz=timezone.utc)
    delta = (now - auth_date).total_seconds()
    if delta > settings.initdata_ttl_seconds:
        raise InitDataError("initData expired")


def _extract_user(data: Dict[str, str]) -> Dict[str, Optional[str]]:
    user_json = data.get("user")
    if not user_json:
        raise InitDataError("User data missing")
    try:
        user_data = json.loads(user_json)
    except json.JSONDecodeError as exc:
        raise InitDataError("Invalid user JSON") from exc
    if "id" not in user_data:
        raise InitDataError("User id missing")
    return {
        "telegram_user_id": int(user_data["id"]),
        "username": user_data.get("username"),
    }


async def authenticate_user(init_data: str, session: AsyncSession) -> User:
    """Validate initData and upsert the user."""
    parsed = _parse_init_data(init_data)
    expected_hash = _calculate_hash(parsed)
    if expected_hash != parsed["hash"]:
        raise InitDataError("Invalid initData hash")
    _validate_auth_date(parsed.get("auth_date"))
    user_payload = _extract_user(parsed)

    stmt = select(User).where(User.telegram_user_id == user_payload["telegram_user_id"])
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(**user_payload)
        session.add(user)
    else:
        user.username = user_payload["username"]

    await session.commit()
    await session.refresh(user)
    return user


async def get_current_user(
    init_data_header: Annotated[Optional[str], Header(alias="X-Telegram-Init-Data")] = None,
    init_data_query: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> User:
    """FastAPI dependency that returns the authenticated user."""
    raw_init_data = init_data_header or init_data_query
    if not raw_init_data:
        raise InitDataError("initData not provided")
    return await authenticate_user(raw_init_data, session)



