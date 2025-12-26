"""Telethon client helpers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from telethon import TelegramClient, events
from telethon.errors import RPCError, BotMethodInvalidError, FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message
from telethon.tl.types import (
    Channel,
    Chat,
    User as TelegramUser,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
)

from .config import get_settings
from .db import SessionLocal
from .models import BotChat, User as DBUser


logger = logging.getLogger(__name__)
settings = get_settings()

# Separate clients: user (for fetching history) and bot (for sending)
_bot_client: Optional[TelegramClient] = None
_user_client: Optional[TelegramClient] = None
_bot_lock = asyncio.Lock()
_user_lock = asyncio.Lock()
_bot_dialogs_loaded = False
_bot_updates_started = False


async def _get_bot_client() -> TelegramClient:
    """Return a started Telethon bot client (singleton)."""
    global _bot_client
    if _bot_client and _bot_client.is_connected():
        return _bot_client
    async with _bot_lock:
        if _bot_client and _bot_client.is_connected():
            return _bot_client
        _bot_client = TelegramClient(
            StringSession(),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        try:
            await _bot_client.start(bot_token=settings.telegram_bot_token)
            logger.info("Telethon bot client started")
        except FloodWaitError as e:
            logger.error(
                "Telegram FloodWait: нужно подождать %d секунд (~%d минут) перед повторной авторизацией бота",
                e.seconds, e.seconds // 60
            )
            raise
        return _bot_client


async def _get_user_client() -> Optional[TelegramClient]:
    """Return a started Telethon user client if TELEGRAM_SESSION is provided."""
    global _user_client
    if not settings.telegram_session:
        return None
    if _user_client and _user_client.is_connected():
        return _user_client
    async with _user_lock:
        if _user_client and _user_client.is_connected():
            return _user_client
        _user_client = TelegramClient(
            StringSession(settings.telegram_session),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await _user_client.start()
        logger.info("Telethon user client started")
        return _user_client


async def _get_fetch_client() -> TelegramClient:
    """Prefer user client for fetching history; fallback to bot client."""
    user_client = await _get_user_client()
    if user_client:
        return user_client
    return await _get_bot_client()


async def resolve_chat(identifier: Union[str, int]) -> int:
    """Resolve chat username or ID into a numeric ID."""
    client = await _get_fetch_client()
    entity = await client.get_entity(identifier)
    return int(entity.id)


async def fetch_messages(
    identifier: Union[str, int],
    from_datetime: Optional[datetime] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Fetch recent messages after from_datetime."""
    client = await _get_fetch_client()
    entity = await client.get_entity(identifier)
    collected: List[Dict[str, Any]] = []

    async for message in client.iter_messages(entity, limit=limit):
        if from_datetime and message.date <= from_datetime:
            break
        if not _is_relevant_message(message):
            continue
        username = getattr(entity, "username", None)
        link = None
        if getattr(message, "link", None):
            link = str(message.link)
        elif username:
            link = f"https://t.me/{username}/{message.id}"
        collected.append(
            {
                "id": message.id,
                "date": message.date,
                "text": message.message or "",
                "source": username or str(entity.id),
                "link": link,
            }
        )
    return list(reversed(collected))


async def list_bot_targets(user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    """Return dialogs the bot can see for a specific user."""
    async with SessionLocal() as session:
        rows = await session.execute(
            BotChat.__table__.select().where(BotChat.user_id == user_id).limit(limit)
        )
        result = rows.mappings().all()
        return [
            {
                "id": str(r["id"]),
                "title": r["title"] or "",
                "username": r["username"],
                "chat_type": r["chat_type"],
                "last_seen_at": r["last_seen_at"],
            }
            for r in result
        ]


async def _get_or_create_user_by_telegram_id(telegram_user_id: int, username: str = None) -> int:
    """Get or create a User record by telegram_user_id, return internal user_id."""
    from sqlalchemy import select
    async with SessionLocal() as session:
        stmt = select(DBUser).where(DBUser.telegram_user_id == telegram_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user.id
        # Create new user
        new_user = DBUser(telegram_user_id=telegram_user_id, username=username)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user.id


async def _upsert_bot_chat(entity, user_id: int) -> None:
    """Store chat where bot has been seen for a specific user (internal user_id)."""
    chat_id = int(getattr(entity, "id"))
    title = getattr(entity, "title", None) or getattr(entity, "first_name", "") or ""
    username = getattr(entity, "username", None)
    chat_type = "user"
    access_hash = getattr(entity, "access_hash", None)
    if isinstance(entity, Channel):
        chat_type = "channel" if entity.broadcast else "supergroup"
        # Correct format: -100 concatenated with channel id
        chat_id = int(f"-100{entity.id}")
        access_hash = getattr(entity, "access_hash", None)
    elif isinstance(entity, Chat):
        chat_type = "group"

    async with SessionLocal() as session:
        from sqlalchemy import select
        stmt = select(BotChat).where(BotChat.id == chat_id, BotChat.user_id == user_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.title = title
            existing.username = username
            existing.chat_type = chat_type
            existing.access_hash = access_hash
            existing.last_seen_at = datetime.now()
        else:
            session.add(
                BotChat(
                    id=chat_id,
                    user_id=user_id,
                    title=title,
                    username=username,
                    chat_type=chat_type,
                    access_hash=access_hash,
                    last_seen_at=datetime.now(),
                )
            )
        await session.commit()


async def _upsert_bot_chat_raw(
    chat_id: int,
    user_id: int,
    title: str,
    username: Optional[str],
    chat_type: str,
    access_hash: Optional[int] = None,
) -> None:
    """Store chat with raw parameters (for private chats without entity)."""
    async with SessionLocal() as session:
        from sqlalchemy import select
        stmt = select(BotChat).where(BotChat.id == chat_id, BotChat.user_id == user_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.title = title
            existing.username = username
            existing.chat_type = chat_type
            existing.access_hash = access_hash
            existing.last_seen_at = datetime.now()
        else:
            session.add(
                BotChat(
                    id=chat_id,
                    user_id=user_id,
                    title=title,
                    username=username,
                    chat_type=chat_type,
                    access_hash=access_hash,
                    last_seen_at=datetime.now(),
                )
            )
        await session.commit()


async def register_chat_for_user(identifier: Union[str, int], user_id: int) -> bool:
    """Try to resolve a chat and register it for a user. Returns True on success."""
    try:
        client = await _get_bot_client()
        entity = await client.get_entity(identifier)
        await _upsert_bot_chat(entity, user_id)
        return True
    except Exception:  # pylint: disable=broad-except
        logger.debug("Could not register chat %s for user %s", identifier, user_id)
        return False


async def send_message(identifier: Union[str, int], text: str) -> None:
    """Send a message via the bot."""
    client = await _get_bot_client()
    entity = None
    # Prefer numeric if it looks like an ID (e.g., -100123...)
    candidates: List[Union[str, int]] = []
    ident_str = str(identifier).strip()
    if ident_str.lstrip("-").isdigit():
        try:
            candidates.append(int(ident_str))
        except Exception:  # pylint: disable=broad-except
            candidates.append(ident_str)
    else:
        candidates.append(identifier)

    last_exc = None
    # Try using stored BotChat access_hash first if numeric id is provided
    if candidates and isinstance(candidates[0], int):
        chat_id = candidates[0]
        stored = None
        async with SessionLocal() as session:
            from sqlalchemy import select
            # BotChat has composite key (id, user_id), so we just find any matching chat_id
            stmt = select(BotChat).where(BotChat.id == chat_id).limit(1)
            result = await session.execute(stmt)
            stored = result.scalar_one_or_none()
        if stored:
            try:
                if stored.chat_type in ("channel", "supergroup"):
                    entity = InputPeerChannel(channel_id=abs(chat_id) % (10**10), access_hash=stored.access_hash or 0)
                elif stored.chat_type == "group":
                    entity = InputPeerChat(chat_id=abs(chat_id))
                elif stored.chat_type in ("user", "private"):
                    entity = InputPeerUser(user_id=abs(chat_id), access_hash=stored.access_hash or 0)
                else:
                    # Unknown type - try as user
                    entity = InputPeerUser(user_id=abs(chat_id), access_hash=stored.access_hash or 0)
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

    if entity is None:
        for cand in candidates:
            try:
                entity = await client.get_entity(cand)
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc
                continue
    # If failed, try to load dialogs to refresh entity cache and retry once
    if entity is None:
        global _bot_dialogs_loaded  # pylint: disable=global-statement
        if not _bot_dialogs_loaded:
            try:
                await client.get_dialogs(limit=2000)
                _bot_dialogs_loaded = True
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc
        for cand in candidates:
            try:
                entity = await client.get_entity(cand)
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc
                continue
    if entity is None:
        logger.exception("Failed to resolve target %s for sending", identifier, exc_info=last_exc)
        raise last_exc or RuntimeError(f"Cannot resolve {identifier}")

    try:
        await client.send_message(entity, text)
    except RPCError:
        logger.exception("Failed to send message to %s", identifier)
        raise


async def ensure_bot_updates_listener() -> None:
    """Start a listener to capture /start commands and register chats."""
    global _bot_updates_started  # pylint: disable=global-statement
    if _bot_updates_started:
        return
    try:
        client = await _get_bot_client()
        
        @client.on(events.NewMessage(pattern=r'^/start'))
        async def handle_start(event):
            """When user sends /start, register the chat for that user."""
            try:
                sender = await event.get_sender()
                chat = event.chat
                
                if not chat:
                    return
                
                chat_type = _get_chat_type(chat)
                
                # Private chat - check for channel ID parameter
                if chat_type == "user":
                    # Parse message for channel ID: /start -100xxx or /start @channel
                    message_text = event.message.text.strip()
                    parts = message_text.split(maxsplit=1)
                    
                    # Always register the private chat with the bot as a target
                    if sender and isinstance(sender, TelegramUser):
                        sender_username = getattr(sender, "username", None)
                        internal_user_id = await _get_or_create_user_by_telegram_id(sender.id, sender_username)
                        
                        # Register private chat (conversation with bot) as target
                        await _upsert_bot_chat_raw(
                            chat_id=sender.id,
                            user_id=internal_user_id,
                            title="📬 Личные сообщения (бот)",
                            username=sender_username,
                            chat_type="private",
                        )
                        logger.info("Registered private chat for user %s (tg: %s)", internal_user_id, sender.id)
                    
                    if len(parts) > 1:
                        # User provided a channel ID to register
                        target_id = parts[1].strip()
                        await _register_channel_from_private_chat(event, sender, target_id)
                    else:
                        # Just /start - show help
                        await event.respond(
                            "👋 Привет! Я бот для создания сводок новостей.\n\n"
                            "✅ **Личные сообщения зарегистрированы!**\n"
                            "Теперь вы можете получать сводки прямо в этом чате.\n\n"
                            "📌 **Как добавить канал или группу:**\n\n"
                            "1. Добавьте бота в канал/группу как администратора\n"
                            "2. Узнайте ID канала через @userinfobot или @getmyid_bot\n"
                            "3. Напишите мне здесь:\n"
                            "   `/start -1002932835607`\n"
                            "   (формат: `-100` + ID канала)\n\n"
                            "Или: `/start @username_канала`\n\n"
                            "После регистрации откройте мини-приложение и выберите чат."
                        )
                    return
                
                # In channel/group - try to register directly
                if sender and isinstance(sender, TelegramUser):
                    sender_username = getattr(sender, "username", None)
                    internal_user_id = await _get_or_create_user_by_telegram_id(sender.id, sender_username)
                    
                    await _upsert_bot_chat(chat, internal_user_id)
                    chat_id_display = _get_chat_id_for_display(chat)
                    logger.info("Registered chat %s (type: %s) for user %s (tg: %s) via /start in chat", 
                                chat_id_display, chat_type, internal_user_id, sender.id)
                    await event.respond(
                        f"✅ {chat_type.capitalize()} зарегистрирован!\n"
                        f"ID: {chat_id_display}\n"
                        f"Теперь вы можете выбрать его в мини-приложении."
                    )
                else:
                    # Anonymous post in channel - show alternative
                    chat_id_display = _get_chat_id_for_display(chat)
                    await event.respond(
                        f"ℹ️ Чтобы зарегистрировать этот чат, напишите боту в ЛС:\n"
                        f"`/start {chat_id_display}`"
                    )
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to handle /start command")
        
        async def _register_channel_from_private_chat(event, sender, target_id: str):
            """Register a channel/group from private chat by ID or username."""
            try:
                # Get internal user_id
                sender_username = getattr(sender, "username", None)
                internal_user_id = await _get_or_create_user_by_telegram_id(sender.id, sender_username)
                
                # Convert string ID to integer if it looks like a number
                resolved_id: Union[int, str] = target_id
                if target_id.lstrip('-').isdigit():
                    resolved_id = int(target_id)
                
                # Try to resolve the target chat
                try:
                    target_entity = await client.get_entity(resolved_id)
                except Exception as e:
                    logger.warning("Failed to resolve target %s: %s", resolved_id, e)
                    await event.respond(
                        f"❌ Не удалось найти чат `{target_id}`.\n\n"
                        "Убедитесь, что:\n"
                        "• ID указан правильно (например, `-1002932835607`)\n"
                        "• Бот добавлен в этот канал/группу как администратор\n"
                        "• Формат: `-100` + ID канала (например, канал 2932835607 → `-1002932835607`)"
                    )
                    return
                
                target_type = _get_chat_type(target_entity)
                
                if target_type == "user":
                    await event.respond(
                        "❌ Это ID пользователя, а не канала/группы.\n"
                        "Укажите ID канала (начинается с -100) или группы (начинается с -)."
                    )
                    return
                
                # Register the channel/group for this user
                await _upsert_bot_chat(target_entity, internal_user_id)
                chat_id_display = _get_chat_id_for_display(target_entity)
                title = getattr(target_entity, 'title', 'Unknown')
                
                logger.info("Registered chat %s '%s' (type: %s) for user %s (tg: %s) via /start in PM", 
                            chat_id_display, title, target_type, internal_user_id, sender.id)
                await event.respond(
                    f"✅ {target_type.capitalize()} зарегистрирован!\n\n"
                    f"📌 **{title}**\n"
                    f"ID: `{chat_id_display}`\n\n"
                    f"Теперь вы можете выбрать его в мини-приложении."
                )
            except Exception as e:
                logger.exception("Failed to register channel from PM: %s", e)
                await event.respond(
                    f"❌ Ошибка при регистрации чата: {e}\n\n"
                    "Убедитесь, что бот добавлен в канал/группу как администратор."
                )
        
        _bot_updates_started = True
        logger.info("Bot /start listener registered")
    except FloodWaitError as e:
        logger.warning(
            "Не удалось запустить бота из-за FloodWait. Подождите %d секунд и перезапустите.",
            e.seconds
        )
        # Don't crash the app, just skip bot initialization for now


def _get_chat_type(entity) -> str:
    """Determine chat type from entity."""
    if isinstance(entity, Channel):
        return "channel" if entity.broadcast else "supergroup"
    elif isinstance(entity, Chat):
        return "group"
    return "user"


def _get_chat_id_for_display(entity) -> str:
    """Get the chat ID in the format suitable for target_chat_id."""
    if isinstance(entity, Channel):
        # String concatenation: -100 + channel_id
        return f"-100{entity.id}"
    elif isinstance(entity, Chat):
        return str(-entity.id)
    else:
        return str(entity.id)


def _is_relevant_message(message: Message) -> bool:
    """Filter service/system messages."""
    if message.action:
        return False
    text = (message.message or "").strip()
    return bool(text)



