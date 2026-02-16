"""Tests for configuration loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from src.config.settings import AppSettings, DuplicateKeyError


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


def test_unicode_decode_error(tmp_path: Path) -> None:
    """AppSettings.load should raise helpful UnicodeDecodeError for invalid encoding."""
    config_yaml = tmp_path / "config.yaml"
    # Write file with invalid UTF-8 byte sequence
    # Byte 0xED at start of a sequence is invalid in UTF-8
    with open(config_yaml, "wb") as f:
        f.write(b"mistral:\n  model: test\xed\xed\xed")

    with pytest.raises(UnicodeDecodeError) as exc_info:
        AppSettings.load(config_dir=tmp_path)

    error_msg = str(exc_info.value)
    assert "encoding error" in error_msg.lower()
    assert "UTF-8" in error_msg or "utf-8" in error_msg.lower()


def test_duplicate_keys_error(tmp_path: Path) -> None:
    """AppSettings.load should detect and report duplicate keys in YAML."""
    config_yaml = tmp_path / "config.yaml"
    # Create YAML with duplicate 'mistral' key
    config_yaml.write_text(
        textwrap.dedent("""\
        mistral:
          model: mistral-small-latest
          temperature: 0.5
        bot:
          username: testbot
        mistral:
          model: mistral-large-latest
          temperature: 0.8
        """)
    )

    with pytest.raises(DuplicateKeyError) as exc_info:
        AppSettings.load(config_dir=tmp_path)

    error_msg = str(exc_info.value)
    assert "duplicate" in error_msg.lower()
    assert "mistral" in error_msg.lower()


def test_invalid_yaml_syntax(tmp_path: Path) -> None:
    """AppSettings.load should raise helpful error for invalid YAML syntax."""
    config_yaml = tmp_path / "config.yaml"
    # Create invalid YAML (unmatched brackets)
    config_yaml.write_text(
        textwrap.dedent("""\
        mistral:
          model: [mistral-small-latest
          temperature: 0.5
        """)
    )

    with pytest.raises(yaml.YAMLError) as exc_info:
        AppSettings.load(config_dir=tmp_path)

    error_msg = str(exc_info.value)
    assert "parse" in error_msg.lower() or "yaml" in error_msg.lower()


def test_duplicate_keys_in_access_file(tmp_path: Path) -> None:
    """AppSettings.load should detect duplicate keys in allowed_users.yaml."""
    access_yaml = tmp_path / "allowed_users.yaml"
    # Create YAML with duplicate key
    access_yaml.write_text(
        textwrap.dedent("""\
        allowed_user_ids: [100, 200]
        allowed_chat_ids: [-1001]
        allowed_user_ids: [300, 400]
        """)
    )

    with pytest.raises(DuplicateKeyError) as exc_info:
        AppSettings.load(config_dir=tmp_path)

    error_msg = str(exc_info.value)
    assert "duplicate" in error_msg.lower()
    assert "allowed_user_ids" in error_msg.lower()


def test_nested_duplicate_keys(tmp_path: Path) -> None:
    """AppSettings.load should detect duplicate keys in nested structures."""
    config_yaml = tmp_path / "config.yaml"
    # Create YAML with duplicate nested key
    config_yaml.write_text(
        textwrap.dedent("""\
        mistral:
          model: mistral-small-latest
          temperature: 0.5
          model: mistral-large-latest
        """)
    )

    with pytest.raises(DuplicateKeyError) as exc_info:
        AppSettings.load(config_dir=tmp_path)

    error_msg = str(exc_info.value)
    assert "duplicate" in error_msg.lower()
    assert "model" in error_msg.lower()
