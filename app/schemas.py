"""Pydantic schemas for API payloads."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class UserRead(BaseModel):
    id: int
    telegram_user_id: int
    username: Optional[str]

    class Config:
        from_attributes = True


class TemplateSourceRead(BaseModel):
    id: int
    source_identifier: str
    source_chat_id: Optional[int]

    class Config:
        from_attributes = True


class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    target_chat: str = Field(alias="target_chat_id", min_length=1, max_length=128)
    frequency_hours: int = Field(..., description="Allowed values: 6, 12, 24")
    is_active: bool = True
    sources: List[str] = Field(default_factory=list, max_length=50)
    custom_prompt: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("frequency_hours")
    @classmethod
    def validate_frequency(cls, value: int) -> int:
        if value not in {6, 12, 24}:
            raise ValueError("frequency_hours must be 6, 12, or 24")
        return value

    @field_validator("target_chat")
    @classmethod
    def validate_target_chat(cls, value: str) -> str:
        """Validate target chat identifier format."""
        value = value.strip()
        if not value:
            raise ValueError("target_chat cannot be empty")
        # Must be @username or numeric ID (possibly negative for groups/channels)
        if not value.startswith("@") and not value.lstrip("-").isdigit():
            raise ValueError("target_chat must be @username or numeric chat ID")
        return value

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: List[str]) -> List[str]:
        """Clean and validate source identifiers."""
        cleaned = []
        for src in value:
            src = src.strip()
            if not src:
                continue
            if not src.startswith("@") and not src.lstrip("-").isdigit():
                raise ValueError(f"Invalid source identifier: {src}")
            cleaned.append(src)
        return cleaned

    class Config:
        populate_by_name = True


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(TemplateBase):
    pass


class TemplateRead(BaseModel):
    id: int
    name: str
    target_chat_id: str
    frequency_hours: int
    is_active: bool
    last_run_at: Optional[datetime]
    sources: List[TemplateSourceRead]
    custom_prompt: Optional[str]

    class Config:
        from_attributes = True


class RunLogRead(BaseModel):
    id: int
    template_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    messages_count: int
    error_message: Optional[str]

    class Config:
        from_attributes = True


class TargetChatRead(BaseModel):
    id: str
    title: str
    username: Optional[str]
    chat_type: str
    last_seen_at: Optional[datetime] = None



