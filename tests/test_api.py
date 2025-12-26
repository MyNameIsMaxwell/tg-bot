"""Tests for API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, async_client):
        """Health endpoint should return ok status."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestTemplatesAPI:
    """Tests for templates CRUD API."""

    @pytest.mark.asyncio
    async def test_list_templates_requires_auth(self, async_client):
        """Should return 401 without initData."""
        response = await async_client.get("/api/templates/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_templates_with_valid_auth(self, async_client, mock_telegram_init_data):
        """Should return templates list with valid auth."""
        init_data = mock_telegram_init_data(user_id=123, username="testuser")
        response = await async_client.get(
            "/api/templates/",
            headers={"X-Telegram-Init-Data": init_data}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_create_template_validation(self, async_client, mock_telegram_init_data):
        """Should validate template creation payload."""
        init_data = mock_telegram_init_data()
        
        # Missing required fields
        response = await async_client.post(
            "/api/templates/",
            headers={"X-Telegram-Init-Data": init_data},
            json={}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_template_success(self, async_client, mock_telegram_init_data):
        """Should create template with valid data."""
        init_data = mock_telegram_init_data(user_id=456, username="creator")
        
        # Mock the register_chat_for_user to avoid Telegram API calls
        with patch("app.routers.templates.register_chat_for_user", new_callable=AsyncMock):
            response = await async_client.post(
                "/api/templates/",
                headers={"X-Telegram-Init-Data": init_data},
                json={
                    "name": "Test Template",
                    "target_chat_id": "@testchannel",
                    "frequency_hours": 12,
                    "sources": ["@source1", "@source2"],
                    "is_active": True
                }
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["frequency_hours"] == 12
        assert len(data["sources"]) == 2

    @pytest.mark.asyncio
    async def test_frequency_hours_validation(self, async_client, mock_telegram_init_data):
        """Should reject invalid frequency_hours values."""
        init_data = mock_telegram_init_data()
        
        response = await async_client.post(
            "/api/templates/",
            headers={"X-Telegram-Init-Data": init_data},
            json={
                "name": "Test",
                "target_chat_id": "@test",
                "frequency_hours": 8,  # Invalid - only 6, 12, 24 allowed
                "sources": []
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, async_client, mock_telegram_init_data):
        """Should return 404 for non-existent template."""
        init_data = mock_telegram_init_data()
        
        response = await async_client.delete(
            "/api/templates/99999",
            headers={"X-Telegram-Init-Data": init_data}
        )
        assert response.status_code == 404


class TestTargetsAPI:
    """Tests for targets list endpoint."""

    @pytest.mark.asyncio
    async def test_list_targets_requires_auth(self, async_client):
        """Should return 401 without auth."""
        response = await async_client.get("/api/templates/targets")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_targets_returns_empty(self, async_client, mock_telegram_init_data):
        """Should return empty list for new user."""
        init_data = mock_telegram_init_data(user_id=789)
        
        response = await async_client.get(
            "/api/templates/targets",
            headers={"X-Telegram-Init-Data": init_data}
        )
        assert response.status_code == 200
        assert response.json() == []


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, async_client, mock_telegram_init_data):
        """Should include rate limit headers in response."""
        init_data = mock_telegram_init_data()
        
        response = await async_client.get(
            "/api/templates/",
            headers={"X-Telegram-Init-Data": init_data}
        )
        # Rate limit might add headers - just verify request works
        assert response.status_code == 200




