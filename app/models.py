"""ORM models for the Telegram summary system."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import BigInteger

from .db import Base


class TimestampMixin:
    """Reusable mixin for created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
    )


class User(TimestampMixin, Base):
    """Telegram user interacting with the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    templates: Mapped[List["Template"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Template(TimestampMixin, Base):
    """Digest template definition."""

    __tablename__ = "templates"
    __table_args__ = (
        Index("ix_template_user_active", "user_id", "is_active"),
        Index("ix_template_scheduler", "is_active", "in_progress", "last_run_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    target_chat_id: Mapped[str] = mapped_column(String(128))
    frequency_hours: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    in_progress: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="templates")
    sources: Mapped[List["TemplateSource"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )
    logs: Mapped[List["RunLog"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class TemplateSource(TimestampMixin, Base):
    """Source channel/chat for a template."""

    __tablename__ = "template_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE")
    )
    source_identifier: Mapped[str] = mapped_column(String(128))
    source_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    template: Mapped["Template"] = relationship(back_populates="sources")


class RunLog(Base):
    """Execution log for template runs."""

    __tablename__ = "run_logs"
    __table_args__ = (
        Index("ix_runlog_template_status", "template_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    messages_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    template: Mapped["Template"] = relationship(back_populates="logs")


class BotChat(TimestampMixin, Base):
    """Chats where the bot has been seen (to allow sending)."""

    __tablename__ = "bot_chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    chat_type: Mapped[str] = mapped_column(String(32))
    access_hash: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
    )

    user: Mapped["User"] = relationship()

