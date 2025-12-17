"""Async scheduler worker that periodically runs templates."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.logging_config import setup_logging
from app.models import Template

from .processor import process_template


logger = logging.getLogger(__name__)
settings = get_settings()


async def main() -> None:
    setup_logging()
    await init_db()
    interval = settings.scheduler_interval_seconds
    logger.info("Scheduler started with %ss interval", interval)
    while True:
        try:
            await _schedule_due_templates()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Scheduler iteration failed")
        await asyncio.sleep(interval)


async def _schedule_due_templates() -> None:
    async with SessionLocal() as session:
        stmt = select(Template).where(
            Template.is_active.is_(True),
            Template.in_progress.is_(False),
        )
        result = await session.execute(stmt)
        candidates: List[Template] = result.scalars().all()
        now = datetime.now(tz=timezone.utc)
        due_templates = []
        for tpl in candidates:
            if is_template_due(tpl, now):
                due_templates.append(tpl)

        if not due_templates:
            return

        ids = []
        for tpl in due_templates:
            tpl.in_progress = True
            ids.append(tpl.id)
        await session.commit()

    for template_id in ids:
        asyncio.create_task(process_template(template_id))
        logger.info("Scheduled template %s", template_id)


if __name__ == "__main__":
    asyncio.run(main())


def is_template_due(template: Template, now: datetime) -> bool:
    """Return True if template should run at the given moment."""
    if template.last_run_at is None:
        return True
    next_run = template.last_run_at + timedelta(hours=template.frequency_hours)
    return now >= next_run

