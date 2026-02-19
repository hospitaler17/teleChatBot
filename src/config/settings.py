"""Application settings loaded from environment variables and YAML config files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yaml.nodes import MappingNode

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


class DuplicateKeyError(yaml.YAMLError):
    """Exception raised when duplicate keys are found in YAML."""

    pass


class SafeLoaderWithDuplicateCheck(yaml.SafeLoader):
    """YAML SafeLoader that detects duplicate keys."""

    pass


def _construct_mapping_no_duplicates(
    loader: SafeLoaderWithDuplicateCheck, node: MappingNode
) -> dict[Any, Any]:
    """Construct a mapping while checking for duplicate keys.

    Args:
        loader: The YAML loader instance
        node: The YAML mapping node to construct

    Returns:
        Constructed mapping dictionary

    Raises:
        DuplicateKeyError: If duplicate keys are detected
    """
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    key_positions: dict[Any, tuple[int, int]] = {}  # Track first occurrence position

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)

        if key in mapping:
            first_line, first_col = key_positions[key]
            raise DuplicateKeyError(
                f"Duplicate key '{key}' found at line {key_node.start_mark.line + 1}, "
                f"column {key_node.start_mark.column + 1}. "
                f"Previous occurrence at line {first_line}, column {first_col}."
            )

        # Store the position of first occurrence
        key_positions[key] = (key_node.start_mark.line + 1, key_node.start_mark.column + 1)

        # Construct value with deep=True to check nested structures recursively
        value = loader.construct_object(value_node, deep=True)
        mapping[key] = value

    return mapping


SafeLoaderWithDuplicateCheck.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping_no_duplicates
)


class MistralSettings(BaseModel):
    """Settings for the Mistral model.

    Attributes:
        model: The Mistral model ID (e.g., "mistral-small-latest", "mistral-medium-latest")
        max_tokens: Maximum number of tokens to generate in the response
        temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
        system_prompt: Optional system prompt to set the assistant's behavior
        enable_web_search: Enable web search to augment responses with current information
        conversation_history_size: Number of previous messages to include in context (default: 10)
        always_append_date: Always append current date to system prompt, regardless of keywords
    """

    model: str = "mistral-small-latest"
    max_tokens: int = 1024
    temperature: float = 0.7
    system_prompt: str = ""
    enable_web_search: bool = False
    conversation_history_size: int = 10
    always_append_date: bool = False


class BotSettings(BaseModel):
    """General bot behaviour settings.

    Attributes:
        username: The bot's Telegram username (without ``@``).
        language: Bot interface language code (default: ``"ru"``).
        max_message_length: Maximum characters per Telegram message (default: 4096).
        cli_mode: Run in CLI mode instead of connecting to Telegram.
        enable_streaming: Enable progressive streaming responses.
        streaming_threshold: Minimum accumulated characters before first streaming
            update is sent (default: 100).
        streaming_update_interval: Seconds between message edit updates during
            streaming (default: 1.0). Keep >= 1.0 to stay within Telegram rate limits.
    """

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
    """Admin user list.

    Attributes:
        user_ids: List of Telegram user IDs with admin privileges.
    """

    user_ids: list[int] = Field(default_factory=list)


class AccessSettings(BaseModel):
    """Allowed users and chats loaded from YAML.

    Attributes:
        allowed_user_ids: List of Telegram user IDs permitted to use the bot
            in private chats.
        allowed_chat_ids: List of Telegram chat IDs (groups/supergroups) where
            the bot is permitted to respond.
        reactions_enabled: Runtime toggle for automatic message reactions.
            Both this flag AND ``ReactionSettings.enabled`` must be ``True``.
        always_append_date_enabled: Runtime toggle for appending the current date
            to the system prompt. Both this flag AND
            ``MistralSettings.always_append_date`` must be ``True``.
    """

    allowed_user_ids: list[int] = Field(default_factory=list)
    allowed_chat_ids: list[int] = Field(default_factory=list)
    reactions_enabled: bool = True  # Runtime toggle for reactions
    always_append_date_enabled: bool = True  # Runtime toggle for always appending date


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
        """Create settings by merging env vars and YAML config files.

        Args:
            config_dir: Directory containing config files. Defaults to CONFIG_DIR.

        Returns:
            AppSettings instance with loaded configuration

        Raises:
            UnicodeDecodeError: If config file has encoding issues
            DuplicateKeyError: If config file has duplicate keys
            yaml.YAMLError: If config file has invalid YAML syntax
        """
        config_dir = config_dir or CONFIG_DIR
        yaml_data: dict = {}
        access_data: dict = {}

        config_path = config_dir / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as fh:
                    loaded = yaml.load(fh, Loader=SafeLoaderWithDuplicateCheck)
                if loaded is None:
                    yaml_data = {}
                elif isinstance(loaded, dict):
                    yaml_data = loaded
                else:
                    error_msg = (
                        f"Top-level YAML structure in {config_path} must be a mapping "
                        f"(dictionary), but found {type(loaded).__name__}. "
                        f"Please ensure config.yaml starts with key-value pairs, e.g. 'mistral:'."
                    )
                    logger.error(error_msg)
                    raise yaml.YAMLError(error_msg)
                logger.info("Loaded config from %s", config_path)
            except UnicodeDecodeError as e:
                error_msg = (
                    f"Failed to read config file {config_path} due to encoding error. "
                    f"The file may contain invalid UTF-8 characters at position {e.start}. "
                    f"Please ensure the file is saved with UTF-8 encoding without BOM. "
                    f"Original error: {e}"
                )
                logger.error(error_msg)
                raise UnicodeDecodeError(
                    e.encoding, e.object, e.start, e.end, error_msg
                ) from e
            except DuplicateKeyError as e:
                error_msg = (
                    f"Configuration file {config_path} contains duplicate keys. "
                    f"This often happens when merging config files or copy-pasting sections. "
                    f"Error: {e}"
                )
                logger.error(error_msg)
                raise DuplicateKeyError(error_msg) from e
            except yaml.YAMLError as e:
                error_msg = (
                    f"Failed to parse configuration file {config_path}. "
                    f"Please check the YAML syntax. Error: {e}"
                )
                logger.error(error_msg)
                raise yaml.YAMLError(error_msg) from e

        access_path = config_dir / "allowed_users.yaml"
        if access_path.exists():
            try:
                with open(access_path, encoding="utf-8") as fh:
                    loaded_access = yaml.load(fh, Loader=SafeLoaderWithDuplicateCheck)
                if loaded_access is None:
                    access_data = {}
                elif isinstance(loaded_access, dict):
                    access_data = loaded_access
                else:
                    error_msg = (
                        f"Top-level YAML structure in {access_path} must be a mapping "
                        f"(dictionary), but found {type(loaded_access).__name__}. "
                        f"Please ensure allowed_users.yaml starts with key-value pairs."
                    )
                    logger.error(error_msg)
                    raise yaml.YAMLError(error_msg)
                logger.info("Loaded access list from %s", access_path)
            except UnicodeDecodeError as e:
                error_msg = (
                    f"Failed to read access file {access_path} due to encoding error. "
                    f"The file may contain invalid UTF-8 characters at position {e.start}. "
                    f"Please ensure the file is saved with UTF-8 encoding without BOM. "
                    f"Original error: {e}"
                )
                logger.error(error_msg)
                raise UnicodeDecodeError(
                    e.encoding, e.object, e.start, e.end, error_msg
                ) from e
            except DuplicateKeyError as e:
                error_msg = (
                    f"Access file {access_path} contains duplicate keys. "
                    f"Error: {e}"
                )
                logger.error(error_msg)
                raise DuplicateKeyError(error_msg) from e
            except yaml.YAMLError as e:
                error_msg = (
                    f"Failed to parse access file {access_path}. "
                    f"Please check the YAML syntax. Error: {e}"
                )
                logger.error(error_msg)
                raise yaml.YAMLError(error_msg) from e

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
            "always_append_date_enabled": self.access.always_append_date_enabled,
        }
        with open(access_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False)
        logger.info("Saved access list to %s", access_path)
