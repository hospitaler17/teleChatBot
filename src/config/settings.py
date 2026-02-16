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
        enable_web_search: Enable web search to augment responses with current information
        conversation_history_size: Number of previous messages to include in context (default: 10)
    """

    model: str = "mistral-small-latest"
    max_tokens: int = 1024
    temperature: float = 0.7
    system_prompt: str = ""
    enable_web_search: bool = False
    conversation_history_size: int = 10


class BotSettings(BaseModel):
    """General bot behaviour settings."""

    username: str = ""
    language: str = "ru"
    max_message_length: int = 4096
    cli_mode: bool = False  # Run in CLI mode instead of Telegram bot
    enable_streaming: bool = True  # Enable progressive message streaming
    streaming_threshold: int = 100  # Minimum response length to enable streaming (in characters)
    streaming_update_interval: float = 1.0  # Seconds between message updates during streaming
    # Note: Telegram has rate limits (~30 edits/sec total, lower per chat).
    # With many concurrent users, use interval >= 1.0 to avoid rate limit errors.


class AdminSettings(BaseModel):
    """Admin user list."""

    user_ids: list[int] = Field(default_factory=list)


class AccessSettings(BaseModel):
    """Allowed users and chats loaded from YAML."""

    allowed_user_ids: list[int] = Field(default_factory=list)
    allowed_chat_ids: list[int] = Field(default_factory=list)
    reactions_enabled: bool = True  # Runtime toggle for reactions


class ReactionSettings(BaseModel):
    """Settings for automatic message reactions.

    Attributes:
        enabled: Whether the reaction feature is enabled by default
        model: The Mistral model to use for mood analysis
        system_prompt: Prompt instructing the model how to analyze mood
        probability: Probability (0.0-1.0) of analyzing a message
        min_words: Minimum word count to trigger analysis
        moods: Dictionary mapping mood names to emoji reactions
    """

    enabled: bool = False
    model: str = "mistral-small-latest"
    system_prompt: str = (
        "Analyze the sentiment and mood of the user's message. "
        "Respond with ONLY ONE word from this list: "
        "positive, negative, neutral, funny, sad, angry, excited, thoughtful. "
        "Do not provide explanations, just the mood word."
    )
    probability: float = 0.3
    min_words: int = 5
    moods: dict[str, str] = Field(
        default_factory=lambda: {
            "positive": "👍",
            "negative": "👎",
            "neutral": "🤔",
            "funny": "😄",
            "sad": "😢",
            "angry": "😠",
            "excited": "🎉",
            "thoughtful": "💭",
        }
    )


class AppSettings(BaseSettings):
    """Root application settings.

    Secrets come from environment variables; everything else is loaded
    from YAML configuration files via :meth:`load`.
    """

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    mistral_api_key: str = ""
    google_api_key: str = ""
    google_search_engine_id: str = ""

    mistral: MistralSettings = Field(default_factory=MistralSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)
    access: AccessSettings = Field(default_factory=AccessSettings)
    reactions: ReactionSettings = Field(default_factory=ReactionSettings)

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

        # Log loaded mistral settings
        mistral_settings = MistralSettings(**yaml_data.get("mistral", {}))
        logger.info(
            "Mistral settings - model: %s, web_search: %s",
            mistral_settings.model,
            mistral_settings.enable_web_search,
        )

        return cls(
            mistral=mistral_settings,
            bot=BotSettings(**yaml_data.get("bot", {})),
            admin=AdminSettings(**yaml_data.get("admin", {})),
            access=AccessSettings(**access_data),
            reactions=ReactionSettings(**yaml_data.get("reactions", {})),
        )

    def save_access(self, config_dir: Path | None = None) -> None:
        """Persist the current access settings back to YAML."""
        config_dir = config_dir or CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        access_path = config_dir / "allowed_users.yaml"
        data = {
            "allowed_user_ids": self.access.allowed_user_ids,
            "allowed_chat_ids": self.access.allowed_chat_ids,
            "reactions_enabled": self.access.reactions_enabled,
        }
        with open(access_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False)
        logger.info("Saved access list to %s", access_path)
