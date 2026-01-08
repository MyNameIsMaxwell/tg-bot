"""Tests for DeepSeek API client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.deepseek_client import (
    summarize_messages,
    _format_posts_for_prompt,
    _build_user_prompt,
    SummaryResult,
)


class TestFormatPostsForPrompt:
    """Tests for _format_posts_for_prompt function."""

    def test_empty_messages(self):
        """Should return empty string for empty list."""
        result = _format_posts_for_prompt([])
        assert result == ""

    def test_single_message_with_link(self):
        """Should format single message with link."""
        messages = [{"text": "Test message", "link": "https://t.me/test/1"}]
        result = _format_posts_for_prompt(messages)
        assert "[Пост 1]" in result
        assert "Test message" in result
        assert "Ссылка: https://t.me/test/1" in result

    def test_single_message_without_link(self):
        """Should format message without link."""
        messages = [{"text": "Test message"}]
        result = _format_posts_for_prompt(messages)
        assert "[Пост 1]" in result
        assert "Test message" in result
        assert "Ссылка:" not in result

    def test_multiple_messages(self):
        """Should format multiple messages with correct numbering."""
        messages = [
            {"text": "First message", "link": "https://t.me/test/1"},
            {"text": "Second message", "link": "https://t.me/test/2"},
            {"text": "Third message"},
        ]
        result = _format_posts_for_prompt(messages)
        assert "[Пост 1]" in result
        assert "[Пост 2]" in result
        assert "[Пост 3]" in result
        assert "First message" in result
        assert "Second message" in result
        assert "Third message" in result

    def test_skips_empty_text(self):
        """Should skip messages with empty text."""
        messages = [
            {"text": "Valid message"},
            {"text": ""},
            {"text": "   "},  # whitespace only
            {"text": "Another valid"},
        ]
        result = _format_posts_for_prompt(messages)
        assert "Valid message" in result
        assert "Another valid" in result
        # Numbering should still be sequential
        assert "[Пост 1]" in result
        assert "[Пост 2]" in result


class TestBuildUserPrompt:
    """Tests for _build_user_prompt function."""

    def test_empty_messages(self):
        """Should return no messages text for empty list."""
        result = _build_user_prompt([])
        assert "Нет новых сообщений" in result

    def test_with_messages(self):
        """Should include posts in prompt template."""
        messages = [{"text": "Test post", "link": "https://t.me/test/1"}]
        result = _build_user_prompt(messages)
        assert "ПОСТЫ ДЛЯ АНАЛИЗА" in result
        assert "Test post" in result
        assert "Составь сводку" in result


class TestSummarizeMessages:
    """Tests for summarize_messages function."""

    @pytest.mark.asyncio
    async def test_empty_messages_returns_immediately(self):
        """Should return early for empty messages without API call."""
        result = await summarize_messages([])
        assert result.text == "Нет новых сообщений."
        assert result.total_tokens == 0

    @pytest.mark.asyncio
    async def test_successful_api_call(self, mock_deepseek_response):
        """Should return SummaryResult on successful API call."""
        messages = [{"text": "Test message", "link": "https://t.me/test/1"}]
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = MagicMock()
        
        with patch("app.deepseek_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await summarize_messages(messages)
            
            assert isinstance(result, SummaryResult)
            assert "📌" in result.text
            assert result.total_tokens == 150

    @pytest.mark.asyncio
    async def test_custom_instructions_appended(self, mock_deepseek_response):
        """Should append custom instructions to system prompt."""
        messages = [{"text": "Test message"}]
        custom = "Focus on technology news"
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = MagicMock()
        
        with patch("app.deepseek_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            await summarize_messages(messages, custom_instructions=custom)
            
            # Check that the custom instructions were included in the payload
            call_args = mock_instance.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            system_content = payload["messages"][0]["content"]
            assert "Дополнительные инструкции" in system_content
            assert custom in system_content

    @pytest.mark.asyncio
    async def test_max_tokens_scales_with_messages(self, mock_deepseek_response):
        """Should adjust max_tokens based on message count."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = MagicMock()
        
        with patch("app.deepseek_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            # Few messages
            few_messages = [{"text": f"Message {i}"} for i in range(2)]
            await summarize_messages(few_messages)
            call_args = mock_instance.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            few_tokens = payload["max_tokens"]
            
            mock_instance.post.reset_mock()
            
            # Many messages
            many_messages = [{"text": f"Message {i}"} for i in range(20)]
            await summarize_messages(many_messages)
            call_args = mock_instance.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            many_tokens = payload["max_tokens"]
            
            # More messages should mean more tokens (up to the cap)
            assert many_tokens >= few_tokens

    @pytest.mark.asyncio
    async def test_api_error_is_raised(self):
        """Should raise exception on API error after retries."""
        import httpx
        
        messages = [{"text": "Test message"}]
        
        with patch("app.deepseek_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            with pytest.raises(httpx.HTTPStatusError):
                await summarize_messages(messages)







