"""Tests for AdminCommandService."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.api.admin_commands import AdminCommandService
from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings


def _settings(
    admin_ids: list[int] | None = None,
    allowed_users: list[int] | None = None,
    allowed_chats: list[int] | None = None,
) -> AppSettings:
    """Helper to create settings."""
    settings = AppSettings(
        mistral_api_key="fake-key",
    )
    if admin_ids:
        settings.admin.user_ids = admin_ids
    if allowed_users:
        settings.access.allowed_user_ids = allowed_users or []
    if allowed_chats:
        settings.access.allowed_chat_ids = allowed_chats or []
    return settings


class TestAdminCommandService:
    """Tests for AdminCommandService."""

    def test_add_user_as_admin(self, tmp_path: Path) -> None:
        """add_user should add user when caller is admin."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.add_user(42, admin_id=1)

        assert success is True
        assert "добавлен" in message
        assert 42 in s.access.allowed_user_ids

    def test_add_user_rejected_for_non_admin(self) -> None:
        """add_user should reject when caller is not admin."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message = service.add_user(42, admin_id=99)

        assert success is False
        assert "прав администратора" in message
        assert 42 not in s.access.allowed_user_ids

    def test_remove_user_as_admin(self, tmp_path: Path) -> None:
        """remove_user should remove user when caller is admin."""
        s = _settings(admin_ids=[1], allowed_users=[42])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.remove_user(42, admin_id=1)

        assert success is True
        assert "удалён" in message
        assert 42 not in s.access.allowed_user_ids

    def test_reactions_on_as_admin(self, tmp_path: Path) -> None:
        """reactions_on should enable reactions when caller is admin."""
        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = False
        s.reactions.enabled = False
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.reactions_on(admin_id=1)

        assert success is True
        assert "включены" in message
        assert s.access.reactions_enabled is True
        assert s.reactions.enabled is True

    def test_reactions_off_as_admin(self, tmp_path: Path) -> None:
        """reactions_off should disable reactions when caller is admin."""
        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = True
        s.reactions.enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.reactions_off(admin_id=1)

        assert success is True
        assert "выключены" in message
        assert s.access.reactions_enabled is False
        assert s.reactions.enabled is False

    def test_reactions_on_enables_both_flags(self, tmp_path: Path) -> None:
        """reactions_on should enable both config and runtime flags."""
        s = _settings(admin_ids=[1])
        s.reactions.enabled = False
        s.access.reactions_enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, _message = service.reactions_on(admin_id=1)

        assert success is True
        assert s.reactions.enabled is True
        assert s.access.reactions_enabled is True

    def test_list_access_as_admin(self) -> None:
        """list_access should return access lists when caller is admin."""
        s = _settings(admin_ids=[1], allowed_users=[10, 20])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message = service.list_access(admin_id=1)

        assert success is True
        assert "10" in message
        assert "20" in message

    def test_is_admin(self) -> None:
        """is_admin should check admin status."""
        s = _settings(admin_ids=[1, 2])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        assert service.is_admin(1) is True
        assert service.is_admin(2) is True
        assert service.is_admin(99) is False

    def test_reasoning_on_as_admin(self, tmp_path: Path) -> None:
        """reasoning_on should enable reasoning mode when caller is admin."""
        s = _settings(admin_ids=[1])
        s.access.reasoning_mode_enabled = False
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.reasoning_on(admin_id=1)

        assert success is True
        assert "включён" in message
        assert s.access.reasoning_mode_enabled is True

    def test_reasoning_off_as_admin(self, tmp_path: Path) -> None:
        """reasoning_off should disable reasoning mode when caller is admin."""
        s = _settings(admin_ids=[1])
        s.access.reasoning_mode_enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.reasoning_off(admin_id=1)

        assert success is True
        assert "выключен" in message
        assert s.access.reasoning_mode_enabled is False

    def test_reasoning_on_rejected_for_non_admin(self) -> None:
        """reasoning_on should reject when caller is not admin."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message = service.reasoning_on(admin_id=99)

        assert success is False
        assert "прав администратора" in message

    def test_reasoning_status_as_admin(self) -> None:
        """reasoning_status should return status when caller is admin."""
        s = _settings(admin_ids=[1])
        s.mistral.reasoning_mode = True
        s.access.reasoning_mode_enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message = service.reasoning_status(admin_id=1)

        assert success is True
        assert "включён" in message

    def test_list_access_includes_reasoning_status(self) -> None:
        """list_access should include reasoning mode status in output."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message = service.list_access(admin_id=1)

        assert success is True
        assert "CoT" in message or "рассуждения" in message
