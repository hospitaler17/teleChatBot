"""Tests for configuration loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.config.settings import AppSettings


def test_defaults() -> None:
    """Settings should have sensible defaults when no files exist."""
    settings = AppSettings.load(config_dir=Path("/tmp/nonexistent"))
    assert settings.mistral.model == "mistral-small-latest"
    assert settings.mistral.max_tokens == 1024
    assert settings.mistral.system_prompt == ""
    assert settings.bot.language == "ru"
    assert settings.access.allowed_user_ids == []
    assert settings.access.allowed_chat_ids == []


def test_load_from_yaml(tmp_path: Path) -> None:
    """Settings should load values from YAML config files."""
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(
        textwrap.dedent("""\
        mistral:
          model: mistral-large-latest
          temperature: 0.5
          system_prompt: "You are a helpful assistant."
        bot:
          username: testbot
        admin:
          user_ids: [111]
        """)
    )
    access_yaml = tmp_path / "allowed_users.yaml"
    access_yaml.write_text(
        textwrap.dedent("""\
        allowed_user_ids: [100, 200]
        allowed_chat_ids: [-1001]
        """)
    )

    settings = AppSettings.load(config_dir=tmp_path)
    assert settings.mistral.model == "mistral-large-latest"
    assert settings.mistral.temperature == 0.5
    assert settings.mistral.system_prompt == "You are a helpful assistant."
    assert settings.bot.username == "testbot"
    assert settings.admin.user_ids == [111]
    assert settings.access.allowed_user_ids == [100, 200]
    assert settings.access.allowed_chat_ids == [-1001]


def test_save_access(tmp_path: Path) -> None:
    """save_access should persist the access lists to YAML."""
    settings = AppSettings.load(config_dir=tmp_path)
    settings.access.allowed_user_ids.append(42)
    settings.access.allowed_chat_ids.append(-999)
    settings.save_access(config_dir=tmp_path)

    reloaded = AppSettings.load(config_dir=tmp_path)
    assert 42 in reloaded.access.allowed_user_ids
    assert -999 in reloaded.access.allowed_chat_ids
