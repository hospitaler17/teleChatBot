"""Tests for BotDatabase – persistent storage of settings, users and groups."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.api.bot_database import BotDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db() -> BotDatabase:
    """Return an in-memory BotDatabase for testing."""
    return BotDatabase(":memory:")


# ---------------------------------------------------------------------------
# Schema / lifecycle
# ---------------------------------------------------------------------------


class TestBotDatabaseSchema:
    def test_creates_tables(self) -> None:
        """Tables must exist after construction."""
        db = _db()
        tables = {
            row[0]
            for row in db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "settings" in tables
        assert "users" in tables
        assert "groups" in tables

    def test_is_empty_after_creation(self) -> None:
        db = _db()
        assert db.is_empty() is True

    def test_close(self) -> None:
        db = _db()
        db.close()
        with pytest.raises(Exception):
            db._conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# initialize_from_config
# ---------------------------------------------------------------------------


class TestInitializeFromConfig:
    def test_seeds_users_chats_and_settings(self) -> None:
        db = _db()
        db.initialize_from_config(
            user_ids=[10, 20],
            chat_ids=[-100, -200],
            reactions_enabled=True,
            web_search_enabled=False,
            reasoning_mode_enabled=True,
        )
        assert set(db.get_users()) == {10, 20}
        assert set(db.get_chats()) == {-100, -200}
        settings = db.get_settings()
        assert settings["reactions_enabled"] is True
        assert settings["web_search_enabled"] is False
        assert settings["reasoning_mode_enabled"] is True

    def test_is_not_empty_after_seed(self) -> None:
        db = _db()
        db.initialize_from_config(
            user_ids=[1],
            chat_ids=[],
            reactions_enabled=False,
            web_search_enabled=False,
            reasoning_mode_enabled=False,
        )
        assert db.is_empty() is False

    def test_idempotent_on_second_call(self) -> None:
        """initialize_from_config uses INSERT OR IGNORE so a second call is safe."""
        db = _db()
        db.initialize_from_config(
            user_ids=[1],
            chat_ids=[-1],
            reactions_enabled=True,
            web_search_enabled=True,
            reasoning_mode_enabled=True,
        )
        # Call again with different data – should NOT overwrite
        db.initialize_from_config(
            user_ids=[2],
            chat_ids=[-2],
            reactions_enabled=False,
            web_search_enabled=False,
            reasoning_mode_enabled=False,
        )
        users = db.get_users()
        assert 1 in users
        assert 2 in users  # second call appended but did not overwrite
        settings = db.get_settings()
        assert settings["reactions_enabled"] is True  # first-write wins


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestUsers:
    def test_add_user(self) -> None:
        db = _db()
        assert db.add_user(42) is True
        assert 42 in db.get_users()

    def test_add_duplicate_user_returns_false(self) -> None:
        db = _db()
        db.add_user(42)
        assert db.add_user(42) is False

    def test_remove_user(self) -> None:
        db = _db()
        db.add_user(42)
        assert db.remove_user(42) is True
        assert 42 not in db.get_users()

    def test_remove_nonexistent_user_returns_false(self) -> None:
        db = _db()
        assert db.remove_user(999) is False

    def test_get_users_empty(self) -> None:
        assert _db().get_users() == []


# ---------------------------------------------------------------------------
# Chats / groups
# ---------------------------------------------------------------------------


class TestChats:
    def test_add_chat(self) -> None:
        db = _db()
        assert db.add_chat(-100) is True
        assert -100 in db.get_chats()

    def test_add_duplicate_chat_returns_false(self) -> None:
        db = _db()
        db.add_chat(-100)
        assert db.add_chat(-100) is False

    def test_remove_chat(self) -> None:
        db = _db()
        db.add_chat(-100)
        assert db.remove_chat(-100) is True
        assert -100 not in db.get_chats()

    def test_remove_nonexistent_chat_returns_false(self) -> None:
        db = _db()
        assert db.remove_chat(-999) is False

    def test_get_chats_empty(self) -> None:
        assert _db().get_chats() == []


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettings:
    def test_set_and_get_setting(self) -> None:
        db = _db()
        db.set_setting("reactions_enabled", True)
        settings = db.get_settings()
        assert settings["reactions_enabled"] is True

    def test_update_existing_setting(self) -> None:
        db = _db()
        db.set_setting("web_search_enabled", True)
        db.set_setting("web_search_enabled", False)
        assert db.get_settings()["web_search_enabled"] is False

    def test_get_settings_empty(self) -> None:
        assert _db().get_settings() == {}


# ---------------------------------------------------------------------------
# sync_from_settings
# ---------------------------------------------------------------------------


class TestSyncFromSettings:
    def test_sync_replaces_all_rows(self) -> None:
        db = _db()
        db.add_user(1)
        db.add_user(2)
        db.add_chat(-1)
        db.sync_from_settings(
            user_ids=[10, 20],
            chat_ids=[-100],
            reactions_enabled=False,
            web_search_enabled=True,
            reasoning_mode_enabled=False,
        )
        assert set(db.get_users()) == {10, 20}
        assert set(db.get_chats()) == {-100}
        s = db.get_settings()
        assert s["reactions_enabled"] is False
        assert s["web_search_enabled"] is True
        assert s["reasoning_mode_enabled"] is False

    def test_sync_with_empty_lists(self) -> None:
        db = _db()
        db.add_user(1)
        db.sync_from_settings(
            user_ids=[],
            chat_ids=[],
            reactions_enabled=True,
            web_search_enabled=False,
            reasoning_mode_enabled=True,
        )
        assert db.get_users() == []
        assert db.get_chats() == []


# ---------------------------------------------------------------------------
# Integration with AppSettings.load()
# ---------------------------------------------------------------------------


class TestAppSettingsDBIntegration:
    """Verify that AppSettings.load() correctly seeds and reads from the DB."""

    def test_load_seeds_db_when_empty(self, tmp_path: Path) -> None:
        """On first run (empty DB), YAML values should be imported to DB."""
        from src.config.settings import AppSettings

        access_yaml = tmp_path / "allowed_users.yaml"
        access_yaml.write_text(
            textwrap.dedent("""\
            allowed_user_ids: [111, 222]
            allowed_chat_ids: [-999]
            reactions_enabled: false
            """)
        )

        db_path = tmp_path / "bot.db"
        settings = AppSettings.load(config_dir=tmp_path, db_path=db_path)

        assert settings._db is not None
        assert set(settings._db.get_users()) == {111, 222}
        assert settings._db.get_chats() == [-999]
        db_settings = settings._db.get_settings()
        assert db_settings["reactions_enabled"] is False

    def test_load_reads_from_db_on_second_start(self, tmp_path: Path) -> None:
        """On subsequent starts, DB values should override YAML."""
        from src.config.settings import AppSettings

        access_yaml = tmp_path / "allowed_users.yaml"
        access_yaml.write_text("allowed_user_ids: [1]\nallowed_chat_ids: []\n")

        db_path = tmp_path / "bot.db"

        # First start – seeds DB from YAML
        s1 = AppSettings.load(config_dir=tmp_path, db_path=db_path)
        assert s1.access.allowed_user_ids == [1]

        # Simulate runtime change: add user via DB directly
        s1._db.add_user(99)
        s1._db.close()

        # Second start – should pick up user 99 from DB (ignoring YAML)
        s2 = AppSettings.load(config_dir=tmp_path, db_path=db_path)
        assert 99 in s2.access.allowed_user_ids

    def test_save_access_syncs_to_db(self, tmp_path: Path) -> None:
        """save_access() should persist changes to both YAML and DB."""
        from src.config.settings import AppSettings

        db_path = tmp_path / "bot.db"
        settings = AppSettings.load(config_dir=tmp_path, db_path=db_path)

        settings.access.allowed_user_ids.append(42)
        settings.access.reactions_enabled = False
        settings.save_access(config_dir=tmp_path)

        assert 42 in settings._db.get_users()
        db_s = settings._db.get_settings()
        assert db_s["reactions_enabled"] is False
