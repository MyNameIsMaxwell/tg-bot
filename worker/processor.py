"""Template processing logic for the scheduler worker."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.deepseek_client import SummaryResult, summarize_messages
from app.models import RunLog, Template
from app.telegram_client import fetch_messages, send_message


logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of template processing."""
    success: bool
    messages_count: int = 0
    total_tokens: int | None = None
    error: str | None = None


async def process_template(
    template_id: int,
    from_datetime_override=None,
) -> ProcessResult:
    """Process a single template: fetch, summarize, send.
    
    Returns ProcessResult with status and statistics.
    """
    # Step 1: Load template data and create run_log in one transaction
    tpl_id: int | None = None
    target_chat: str = ""
    sources_data: List[dict] = []
    from_dt = from_datetime_override
    run_log_id: int | None = None
    custom_prompt: str | None = None
    
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
            return ProcessResult(success=False, error="Template not found")

        # Store all values we need
        tpl_id = template.id
        target_chat = template.target_chat_id
        custom_prompt = template.custom_prompt
        sources_data = [
            {"identifier": s.source_identifier, "chat_id": s.source_chat_id}
            for s in template.sources
        ]
        if from_dt is None:
            from_dt = template.last_run_at

        # Create and COMMIT the run_log immediately
        run_log = RunLog(template_id=tpl_id, status="running")
        session.add(run_log)
        await session.commit()
        run_log_id = run_log.id
    
    # Step 2: Do all the async work (fetch, summarize, send)
    messages_count = 0
    total_tokens: int | None = None
    error_message: str | None = None
    
    try:
        messages = await _collect_messages_from_data(sources_data, from_dt)
        
        if not messages:
            logger.info("Template %s: no new messages", tpl_id)
            # Update status to success with 0 messages
            await _finalize_template_run(
                template_id, run_log_id, 
                success=True, messages_count=0
            )
            return ProcessResult(success=True, messages_count=0)

        summary_result: SummaryResult = await summarize_messages(
            messages, custom_instructions=custom_prompt
        )
        summary_text = summary_result.text
        total_tokens = summary_result.total_tokens
        messages_count = len(messages)
        
        logger.info(
            "DeepSeek tokens prompt=%s completion=%s total=%s",
            summary_result.prompt_tokens,
            summary_result.completion_tokens,
            total_tokens,
        )
        
        await send_message(target_chat, summary_text)
        
        # Success - update template and run_log
        await _finalize_template_run(
            template_id, run_log_id,
            success=True, messages_count=messages_count
        )
        logger.info("Template %s processed successfully", tpl_id)
        
        return ProcessResult(
            success=True,
            messages_count=messages_count,
            total_tokens=total_tokens,
        )
        
    except Exception as exc:  # pylint: disable=broad-except
        error_message = str(exc)
        logger.exception("Template %s failed: %s", tpl_id, exc)
        
        # Update status to error
        await _finalize_template_run(
            template_id, run_log_id,
            success=False, error_message=error_message
        )
        
        return ProcessResult(success=False, error=error_message)


async def _finalize_template_run(
    template_id: int,
    run_log_id: int | None,
    success: bool,
    messages_count: int = 0,
    error_message: str | None = None,
) -> None:
    """Update template and run_log status after processing."""
    try:
        async with SessionLocal() as session:
            # Update template
            stmt = select(Template).where(Template.id == template_id)
            result = await session.execute(stmt)
            template = result.scalar_one_or_none()
            if template:
                template.in_progress = False
                if success:
                    template.last_run_at = datetime.now(tz=timezone.utc)
            
            # Update run_log if we have one
            if run_log_id:
                stmt = select(RunLog).where(RunLog.id == run_log_id)
                result = await session.execute(stmt)
                run_log = result.scalar_one_or_none()
                if run_log:
                    run_log.status = "success" if success else "error"
                    run_log.messages_count = messages_count
                    run_log.finished_at = datetime.now(tz=timezone.utc)
                    if error_message:
                        run_log.error_message = error_message
            
            await session.commit()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to finalize template %s: %s", template_id, exc)


async def _collect_messages_from_data(
    sources_data: List[dict], last_run_at
) -> List[dict]:
    """Collect messages from source data (not ORM objects)."""
    collected: List[dict] = []
    for source in sources_data:
        identifier = source.get("identifier")
        chat_id = source.get("chat_id")
        
        # Try identifier first, then chat_id
        candidates = []
        if identifier:
            candidates.append(identifier)
        if chat_id:
            candidates.append(chat_id)
        
        for candidate in candidates:
            try:
                messages = await fetch_messages(candidate, from_datetime=last_run_at)
                collected.extend(messages)
                break
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to fetch messages for %s: %s", candidate, exc)
                continue
    
    return collected



