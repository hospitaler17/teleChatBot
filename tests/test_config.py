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
    assert settings.access.reactions_enabled is True  # Default
    assert settings.reactions.enabled is False  # Default - disabled
    assert settings.reactions.model == "mistral-small-latest"
    assert settings.reactions.probability == 0.3
    assert settings.reactions.min_words == 5


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
        reactions:
          enabled: true
          model: "mistral-small-latest"
          probability: 0.5
          min_words: 10
          moods:
            happy: "😊"
            sad: "😢"
        """)
    )
    access_yaml = tmp_path / "allowed_users.yaml"
    access_yaml.write_text(
        textwrap.dedent("""\
        allowed_user_ids: [100, 200]
        allowed_chat_ids: [-1001]
        reactions_enabled: false
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
    assert settings.access.reactions_enabled is False
    assert settings.reactions.enabled is True
    assert settings.reactions.probability == 0.5
    assert settings.reactions.min_words == 10
    assert settings.reactions.moods["happy"] == "😊"
    assert settings.reactions.moods["sad"] == "😢"


def test_save_access(tmp_path: Path) -> None:
    """save_access should persist the access lists to YAML."""
    settings = AppSettings.load(config_dir=tmp_path)
    settings.access.allowed_user_ids.append(42)
    settings.access.allowed_chat_ids.append(-999)
    settings.access.reactions_enabled = False
    settings.save_access(config_dir=tmp_path)

    reloaded = AppSettings.load(config_dir=tmp_path)
    assert 42 in reloaded.access.allowed_user_ids
    assert -999 in reloaded.access.allowed_chat_ids
    assert reloaded.access.reactions_enabled is False
