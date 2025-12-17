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
    name: str
    target_chat: str = Field(alias="target_chat_id")
    frequency_hours: int = Field(..., description="Allowed values: 6, 12, 24")
    is_active: bool = True
    sources: List[str] = Field(default_factory=list)

    @field_validator("frequency_hours")
    @classmethod
    def validate_frequency(cls, value: int) -> int:
        if value not in {6, 12, 24}:
            raise ValueError("frequency_hours must be 6, 12, or 24")
        return value

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



