"""Template processing logic for the scheduler worker."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Union

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.deepseek_client import SummaryResult, summarize_messages
from app.models import RunLog, Template, TemplateSource
from app.telegram_client import fetch_messages, resolve_chat, send_message


logger = logging.getLogger(__name__)


def _parse_identifier(value: str) -> Union[str, int]:
    value = value.strip()
    if value.startswith("@"):
        return value
    if value.lstrip("-").isdigit():
        return int(value)
    return value


async def process_template(
    template_id: int,
    from_datetime_override=None,
    requester_user_id: int | None = None,
) -> None:
    """Process a single template: fetch, summarize, send."""
    async with SessionLocal() as session:
        stmt = (
            select(Template)
            .where(Template.id == template_id)
            .options(selectinload(Template.sources))
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()
        if template is None:
            logger.warning("Template %s not found", template_id)
            return

        run_log = RunLog(template_id=template.id, status="running")
        session.add(run_log)
        await session.flush()

        try:
            from_dt = from_datetime_override or template.last_run_at
            messages = await _collect_messages(template.sources, from_dt)
            if not messages:
                template.last_run_at = datetime.now(tz=timezone.utc)
                template.in_progress = False
                run_log.status = "success"
                run_log.messages_count = 0
                await session.commit()
                logger.info("Template %s: no new messages", template.id)
                return

            summary_result: SummaryResult = await summarize_messages(messages)
            summary_text = summary_result.text
            logger.info(
                "DeepSeek tokens prompt=%s completion=%s total=%s",
                summary_result.prompt_tokens,
                summary_result.completion_tokens,
                summary_result.total_tokens,
            )
            target = template.target_chat_id
            await send_message(target, summary_text)
            if requester_user_id and summary_result.total_tokens is not None:
                info_msg = (
                    f"[INFO] tokens: total={summary_result.total_tokens}, "
                    f"prompt={summary_result.prompt_tokens}, "
                    f"completion={summary_result.completion_tokens}"
                )
                try:
                    await send_message(requester_user_id, info_msg)
                except Exception:  # pylint: disable=broad-except
                    logger.exception("Failed to send info tokens to requester %s", requester_user_id)

            template.last_run_at = datetime.now(tz=timezone.utc)
            template.in_progress = False
            run_log.status = "success"
            run_log.messages_count = len(messages)
            run_log.finished_at = datetime.now(tz=timezone.utc)
            await session.commit()
            logger.info("Template %s processed successfully", template.id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Template %s failed: %s", template.id, exc)
            run_log.status = "error"
            run_log.error_message = str(exc)
            run_log.finished_at = datetime.now(tz=timezone.utc)
            template.in_progress = False
            await session.commit()


async def _collect_messages(
    sources: List[TemplateSource], last_run_at
) -> List[dict]:
    collected: List[dict] = []
    for source in sources:
        # Prefer human-readable identifier first (e.g., @channel), then stored id
        identifiers = []
        if source.source_identifier:
            identifiers.append(source.source_identifier)
        if source.source_chat_id:
            identifiers.append(source.source_chat_id)

        fetched = False
        for candidate in identifiers or [source.source_identifier, source.source_chat_id]:
            if not candidate:
                continue
            try:
                messages = await fetch_messages(candidate, from_datetime=last_run_at)
                collected.extend(messages)
                # Cache resolved chat_id if we used a string identifier
                if source.source_chat_id is None and isinstance(candidate, str):
                    try:
                        source.source_chat_id = await resolve_chat(candidate)
                    except Exception:  # pylint: disable=broad-except
                        pass
                fetched = True
                break
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to fetch messages for %s: %s", candidate, exc)
                # If numeric id is stale/unusable, drop it to force re-resolve later
                if candidate == source.source_chat_id:
                    source.source_chat_id = None
                continue
        if not fetched:
            logger.error(
                "No messages fetched for source %s (id=%s)",
                source.source_identifier,
                source.source_chat_id,
            )
    return collected



