"""Tests for CLI admin command integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli.cli_chat import CLIChat
from src.config.settings import AppSettings


def _settings(
    admin_ids: list[int] | None = None, allowed_users: list[int] | None = None
) -> AppSettings:
    """Helper to create settings."""
    settings = AppSettings(
        mistral_api_key="fake-key",
    )
    if admin_ids:
        settings.admin.user_ids = admin_ids
    if allowed_users:
        settings.access.allowed_user_ids = allowed_users
    return settings


class TestCLIChatAdminCommands:
    """Tests for CLI admin command integration."""

    @pytest.mark.asyncio
    async def test_cli_admin_reactions_on(self, tmp_path: Path) -> None:
        """CLI should be able to enable reactions."""
        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = False

        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            chat = CLIChat(s)
            result = await chat.handle_message("/admin_reactions_on")

        assert result is None  # Command handling returns None
        assert s.access.reactions_enabled is True

    @pytest.mark.asyncio
    async def test_cli_admin_reactions_off(self, tmp_path: Path) -> None:
        """CLI should be able to disable reactions."""
        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = True

        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            chat = CLIChat(s)
            result = await chat.handle_message("/admin_reactions_off")

        assert result is None  # Command handling returns None
        assert s.access.reactions_enabled is False

    @pytest.mark.asyncio
    async def test_cli_admin_reactions_status(self) -> None:
        """CLI should be able to check reactions status."""
        s = _settings(admin_ids=[1])
        chat = CLIChat(s)

        result = await chat.handle_message("/admin_reactions_status")

        assert result is None  # Command handling returns None

    @pytest.mark.asyncio
    async def test_cli_admin_list(self) -> None:
        """CLI should be able to list access settings."""
        s = _settings(admin_ids=[1], allowed_users=[10, 20])
        chat = CLIChat(s)

        result = await chat.handle_message("/admin_list")

        assert result is None  # Command handling returns None

    @pytest.mark.asyncio
    async def test_cli_auto_grants_admin_when_empty(self, tmp_path: Path) -> None:
        """CLI should automatically grant admin rights to user_id=1 when admin list is empty."""
        # Start with no admin IDs
        s = _settings(admin_ids=None)
        assert s.admin.user_ids == []

        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            chat = CLIChat(s)

        # Verify user_id 1 was automatically added to admin list
        assert 1 in s.admin.user_ids

        # Verify admin commands work for user_id 1
        result = await chat.handle_message("/admin_reactions_on")
        assert result is None  # Command handling returns None
        assert s.access.reactions_enabled is True


class TestCLIChatStatusMessages:
    """Tests for CLI status message output."""

    @pytest.mark.asyncio
    async def test_cli_prints_thinking_status(self, capsys: pytest.CaptureFixture) -> None:
        """CLI should print thinking status before generating response."""
        from unittest.mock import AsyncMock, MagicMock

        s = _settings()
        s.bot.enable_streaming = False
        chat = CLIChat(s)

        # Mock the Mistral client
        mock_response = MagicMock()
        mock_response.content = "Hello!"
        mock_response.model = "mistral-small-latest"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 3
        mock_response.total_tokens = 8
        chat.client.generate = AsyncMock(return_value=mock_response)
        chat.client._web_search = None
        chat.client._should_use_web_search = MagicMock(return_value=False)

        await chat.handle_message("Hi")

        captured = capsys.readouterr()
        assert s.status_messages.thinking in captured.out

    @pytest.mark.asyncio
    async def test_cli_prints_search_status_for_web_queries(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """CLI should print search status when web search will be used."""
        from unittest.mock import AsyncMock, MagicMock

        s = _settings()
        s.bot.enable_streaming = False
        chat = CLIChat(s)

        mock_response = MagicMock()
        mock_response.content = "Here are the news..."
        mock_response.model = "mistral-small-latest"
        mock_response.input_tokens = 10
        mock_response.output_tokens = 20
        mock_response.total_tokens = 30
        chat.client.generate = AsyncMock(return_value=mock_response)
        chat.client._web_search = MagicMock()
        chat.client._should_use_web_search = MagicMock(return_value=True)

        await chat.handle_message("новости сегодня")

        captured = capsys.readouterr()
        assert s.status_messages.searching in captured.out
