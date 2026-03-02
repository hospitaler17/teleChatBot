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
        s.mistral.reasoning_mode = False
        s.access.reasoning_mode_enabled = False
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            success, message = service.reasoning_on(admin_id=1)

        assert success is True
        assert "включён" in message
        assert s.access.reasoning_mode_enabled is True
        assert s.mistral.reasoning_mode is True

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

    def test_date_on_then_status_shows_enabled(self, tmp_path: Path) -> None:
        """date_status should show enabled after date_on is called."""
        s = _settings(admin_ids=[1])
        s.mistral.always_append_date = False
        s.access.always_append_date_enabled = False
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            service.date_on(admin_id=1)

        success, message = service.date_status(admin_id=1)
        assert success is True
        assert "включено ✅" in message

    def test_date_off_then_status_shows_disabled(self, tmp_path: Path) -> None:
        """date_status should show disabled after date_off is called."""
        s = _settings(admin_ids=[1])
        s.mistral.always_append_date = True
        s.access.always_append_date_enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            service.date_off(admin_id=1)

        success, message = service.date_status(admin_id=1)
        assert success is True
        assert "выключено ❌" in message

    def test_reactions_on_then_status_shows_enabled(self, tmp_path: Path) -> None:
        """reactions_status should show enabled after reactions_on is called."""
        s = _settings(admin_ids=[1])
        s.reactions.enabled = False
        s.access.reactions_enabled = False
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            service.reactions_on(admin_id=1)

        success, message = service.reactions_status(admin_id=1)
        assert success is True
        assert "включены ✅" in message

    def test_reactions_off_then_status_shows_disabled(self, tmp_path: Path) -> None:
        """reactions_status should show disabled after reactions_off is called."""
        s = _settings(admin_ids=[1])
        s.reactions.enabled = True
        s.access.reactions_enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            service.reactions_off(admin_id=1)

        success, message = service.reactions_status(admin_id=1)
        assert success is True
        assert "выключены ❌" in message

    def test_reasoning_on_then_status_shows_enabled(self, tmp_path: Path) -> None:
        """reasoning_status should show enabled after reasoning_on is called."""
        s = _settings(admin_ids=[1])
        s.mistral.reasoning_mode = False
        s.access.reasoning_mode_enabled = False
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            service.reasoning_on(admin_id=1)

        success, message = service.reasoning_status(admin_id=1)
        assert success is True
        assert "включён ✅" in message

    def test_reasoning_off_then_status_shows_disabled(self, tmp_path: Path) -> None:
        """reasoning_status should show disabled after reasoning_off is called."""
        s = _settings(admin_ids=[1])
        s.mistral.reasoning_mode = True
        s.access.reasoning_mode_enabled = True
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.config.settings.CONFIG_DIR", tmp_path)
            service.reasoning_off(admin_id=1)

        success, message = service.reasoning_status(admin_id=1)
        assert success is True
        assert "выключен ❌" in message

    def test_list_access_includes_reasoning_status(self) -> None:
        """list_access should include reasoning mode status in output."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message = service.list_access(admin_id=1)

        assert success is True
        assert "CoT" in message or "рассуждения" in message


class TestCreateBackup:
    """Tests for AdminCommandService.create_backup."""

    def test_backup_rejected_for_non_admin(self) -> None:
        """create_backup should reject when caller is not admin."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        success, message, zip_path = service.create_backup(admin_id=99)

        assert success is False
        assert "прав администратора" in message
        assert zip_path is None

    def test_backup_creates_zip_with_existing_files(self, tmp_path: Path) -> None:
        """create_backup should return a valid zip archive when files exist."""
        import zipfile

        # Create a fake DB file and config file in tmp_path
        db_file = tmp_path / "conversation_history.db"
        db_file.write_bytes(b"sqlite3-data")
        config_file = tmp_path / "allowed_users.yaml"
        config_file.write_text("allowed_user_ids: []\n")

        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.api.admin_commands.DEFAULT_DB_PATH", db_file)
            mp.setattr("src.api.admin_commands.CONFIG_DIR", tmp_path)
            success, message, zip_path = service.create_backup(admin_id=1)

        try:
            assert success is True
            assert zip_path is not None
            assert zip_path.exists()
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            assert any("conversation_history.db" in n for n in names)
            assert any("allowed_users.yaml" in n for n in names)
        finally:
            if zip_path is not None and zip_path.exists():
                zip_path.unlink(missing_ok=True)

    def test_backup_with_no_existing_files(self, tmp_path: Path) -> None:
        """create_backup should report no files when nothing exists."""
        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        nonexistent_db = tmp_path / "no_db.db"
        empty_config_dir = tmp_path / "empty_config"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.api.admin_commands.DEFAULT_DB_PATH", nonexistent_db)
            mp.setattr("src.api.admin_commands.CONFIG_DIR", empty_config_dir)
            success, message, zip_path = service.create_backup(admin_id=1)

        assert success is False
        assert zip_path is None

    def test_backup_includes_extra_paths(self, tmp_path: Path) -> None:
        """create_backup should include extra_paths in the archive."""
        import zipfile

        db_file = tmp_path / "conversation_history.db"
        db_file.write_bytes(b"data")
        extra_file = tmp_path / "extra.log"
        extra_file.write_text("log data")

        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        service = AdminCommandService(s, af)

        empty_config = tmp_path / "cfg"
        empty_config.mkdir()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.api.admin_commands.DEFAULT_DB_PATH", db_file)
            mp.setattr("src.api.admin_commands.CONFIG_DIR", empty_config)
            success, message, zip_path = service.create_backup(
                admin_id=1, extra_paths=[extra_file]
            )

        try:
            assert success is True
            assert zip_path is not None
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            assert any("extra.log" in n for n in names)
        finally:
            if zip_path is not None and zip_path.exists():
                zip_path.unlink(missing_ok=True)
