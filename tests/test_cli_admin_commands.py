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
