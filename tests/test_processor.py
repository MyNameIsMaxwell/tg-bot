"""Tests for template processor."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from worker.processor import process_template, _collect_messages


class TestProcessTemplate:
    """Tests for process_template function."""

    @pytest.mark.asyncio
    async def test_process_nonexistent_template(self, test_db):
        """Should handle non-existent template gracefully."""
        # Should not raise, just log and return
        await process_template(99999)

    @pytest.mark.asyncio
    async def test_process_template_no_messages(self, test_db, mock_telegram_init_data):
        """Should complete successfully when no new messages."""
        from app.db import SessionLocal
        from app.models import Template, User
        
        # Create test user and template
        async with SessionLocal() as session:
            user = User(telegram_user_id=111, username="proctest")
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            template = Template(
                user_id=user.id,
                name="Test Processor",
                target_chat_id="@test",
                frequency_hours=6,
                is_active=True,
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            template_id = template.id

        # Mock fetch_messages to return empty
        with patch("worker.processor.fetch_messages", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            
            await process_template(template_id)
            
        # Verify template was updated
        async with SessionLocal() as session:
            from sqlalchemy import select
            stmt = select(Template).where(Template.id == template_id)
            result = await session.execute(stmt)
            updated = result.scalar_one()
            assert updated.in_progress is False
            assert updated.last_run_at is not None


class TestCollectMessages:
    """Tests for _collect_messages helper."""

    @pytest.mark.asyncio
    async def test_collect_from_multiple_sources(self):
        """Should aggregate messages from all sources."""
        from app.models import TemplateSource
        
        sources = [
            MagicMock(source_identifier="@channel1", source_chat_id=None),
            MagicMock(source_identifier="@channel2", source_chat_id=None),
        ]
        
        with patch("worker.processor.fetch_messages", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                [{"text": "Msg 1", "link": "https://t.me/c1/1"}],
                [{"text": "Msg 2", "link": "https://t.me/c2/1"}],
            ]
            
            result = await _collect_messages(sources, None)
            
            assert len(result) == 2
            assert any(m["text"] == "Msg 1" for m in result)
            assert any(m["text"] == "Msg 2" for m in result)

    @pytest.mark.asyncio
    async def test_handles_source_error(self):
        """Should continue processing even if one source fails."""
        sources = [
            MagicMock(source_identifier="@channel1", source_chat_id=None),
            MagicMock(source_identifier="@channel2", source_chat_id=None),
        ]
        
        with patch("worker.processor.fetch_messages", new_callable=AsyncMock) as mock_fetch:
            # First source fails, second succeeds
            mock_fetch.side_effect = [
                Exception("Network error"),
                [{"text": "Msg from channel2"}],
            ]
            
            result = await _collect_messages(sources, None)
            
            # Should still get messages from channel2
            assert len(result) == 1
            assert result[0]["text"] == "Msg from channel2"







