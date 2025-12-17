"""Templates CRUD endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import asyncio
from datetime import datetime, timedelta, timezone

from ..auth import get_current_user
from ..db import get_session
from ..models import Template, TemplateSource, User
from ..schemas import TemplateCreate, TemplateRead, TemplateUpdate
from worker.processor import process_template
from app.telegram_client import list_bot_targets, register_chat_for_user
from ..schemas import TargetChatRead

router = APIRouter(prefix="/api/templates", tags=["templates"])


async def _get_template(
    template_id: int, user: User, session: AsyncSession
) -> Template:
    stmt = (
        select(Template)
        .where(Template.id == template_id, Template.user_id == user.id)
        .options(selectinload(Template.sources))
    )
    result = await session.execute(stmt)
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.get("/", response_model=List[TemplateRead])
async def list_templates(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[TemplateRead]:
    stmt = (
        select(Template)
        .where(Template.user_id == current_user.id)
        .options(selectinload(Template.sources))
        .order_by(Template.id)
    )
    result = await session.scalars(stmt)
    templates = result.all()
    return [TemplateRead.model_validate(t) for t in templates]


@router.post("/", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_in: TemplateCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    template = Template(
        user_id=current_user.id,
        name=template_in.name,
        target_chat_id=template_in.target_chat,
        frequency_hours=template_in.frequency_hours,
        is_active=template_in.is_active,
    )
    sources = [
        TemplateSource(source_identifier=src.strip())
        for src in template_in.sources
        if src.strip()
    ]
    template.sources = sources
    session.add(template)
    await session.commit()
    await session.refresh(template)
    # Try to register the target chat for this user
    asyncio.create_task(register_chat_for_user(template_in.target_chat, current_user.id))
    return TemplateRead.model_validate(template)


@router.put("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: int,
    template_in: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    template = await _get_template(template_id, current_user, session)
    template.name = template_in.name
    template.target_chat_id = template_in.target_chat
    template.frequency_hours = template_in.frequency_hours
    template.is_active = template_in.is_active

    existing_sources = {src.source_identifier: src for src in template.sources}
    template.sources.clear()
    for src in template_in.sources:
        src = src.strip()
        if not src:
            continue
        if src in existing_sources:
            template.sources.append(existing_sources[src])
        else:
            template.sources.append(TemplateSource(source_identifier=src))

    await session.commit()
    await session.refresh(template)
    # Try to register the target chat for this user
    asyncio.create_task(register_chat_for_user(template_in.target_chat, current_user.id))
    return TemplateRead.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    template = await _get_template(template_id, current_user, session)
    await session.delete(template)
    await session.commit()


@router.post("/{template_id}/toggle", response_model=TemplateRead)
async def toggle_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    template = await _get_template(template_id, current_user, session)
    template.is_active = not template.is_active
    await session.commit()
    await session.refresh(template)
    return TemplateRead.model_validate(template)


@router.post("/{template_id}/run-now", status_code=status.HTTP_202_ACCEPTED)
async def run_template_now(
    template_id: int,
    hours_back: int | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    """Trigger immediate processing of a template."""
    template = await _get_template(template_id, current_user, session)
    if template.in_progress:
        return TemplateRead.model_validate(template)
    template.in_progress = True
    await session.commit()

    from_dt = None
    if hours_back:
        from_dt = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)

    asyncio.create_task(
        process_template(
            template.id,
            from_datetime_override=from_dt,
            requester_user_id=current_user.telegram_user_id,
        )
    )
    return TemplateRead.model_validate(template)


@router.get("/targets", response_model=List[TargetChatRead])
async def list_targets(
    current_user: User = Depends(get_current_user),
) -> List[TargetChatRead]:
    """List chats where the bot can write (only chats registered by this user)."""
    targets = await list_bot_targets(user_id=current_user.id)
    return [TargetChatRead(**t) for t in targets]



