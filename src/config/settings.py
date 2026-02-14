"""Application settings loaded from environment variables and YAML config files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


class MistralSettings(BaseModel):
    """Settings for the Mistral model.

    Attributes:
        model: The Mistral model ID (e.g., "mistral-small-latest", "mistral-medium-latest")
        max_tokens: Maximum number of tokens to generate in the response
        temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
        system_prompt: Optional system prompt to set the assistant's behavior
    """

    model: str = "mistral-small-latest"
    max_tokens: int = 1024
    temperature: float = 0.7
    system_prompt: str = ""


class BotSettings(BaseModel):
    """General bot behaviour settings."""

    username: str = ""
    language: str = "ru"
    max_message_length: int = 4096


class AdminSettings(BaseModel):
    """Admin user list."""

    user_ids: list[int] = Field(default_factory=list)


class AccessSettings(BaseModel):
    """Allowed users and chats loaded from YAML."""

    allowed_user_ids: list[int] = Field(default_factory=list)
    allowed_chat_ids: list[int] = Field(default_factory=list)


class AppSettings(BaseSettings):
    """Root application settings.

    Secrets come from environment variables; everything else is loaded
    from YAML configuration files via :meth:`load`.
    """

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    mistral_api_key: str = ""

    mistral: MistralSettings = Field(default_factory=MistralSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)
    access: AccessSettings = Field(default_factory=AccessSettings)

    @classmethod
    def load(cls, config_dir: Path | None = None) -> Self:
        """Create settings by merging env vars and YAML config files."""
        config_dir = config_dir or CONFIG_DIR
        yaml_data: dict = {}
        access_data: dict = {}

        config_path = config_dir / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as fh:
                yaml_data = yaml.safe_load(fh) or {}
            logger.info("Loaded config from %s", config_path)

        access_path = config_dir / "allowed_users.yaml"
        if access_path.exists():
            with open(access_path, encoding="utf-8") as fh:
                access_data = yaml.safe_load(fh) or {}
            logger.info("Loaded access list from %s", access_path)

        return cls(
            mistral=MistralSettings(**yaml_data.get("mistral", {})),
            bot=BotSettings(**yaml_data.get("bot", {})),
            admin=AdminSettings(**yaml_data.get("admin", {})),
            access=AccessSettings(**access_data),
        )

    def save_access(self, config_dir: Path | None = None) -> None:
        """Persist the current access settings back to YAML."""
        config_dir = config_dir or CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        access_path = config_dir / "allowed_users.yaml"
        data = {
            "allowed_user_ids": self.access.allowed_user_ids,
            "allowed_chat_ids": self.access.allowed_chat_ids,
        }
        with open(access_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False)
        logger.info("Saved access list to %s", access_path)
