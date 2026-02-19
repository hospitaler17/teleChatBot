"""Access control filter for the Telegram bot."""

from __future__ import annotations

import logging

from telegram import Message, Update

from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class AccessFilter:
    """Decides whether an incoming update should be processed.

    Rules
    -----
    * **Private chats** – the user must be in the allowed-user list *or* be an admin.
    * **Group / supergroup chats** – the chat must be in the allowed-chat list
      *and* the message must mention the bot directly (reply or ``@bot_username``).
    """

    def __init__(self, settings: AppSettings) -> None:
        """Initialize access filter.

        Args:
            settings: Application settings containing admin user IDs
                and allowed users/chats lists.
        """
        self._settings = settings

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_admin(self, user_id: int) -> bool:
        """Return ``True`` if *user_id* is in the admin list."""
        return user_id in self._settings.admin.user_ids

    def is_allowed_user(self, user_id: int) -> bool:
        """Return ``True`` if *user_id* is allowed in private chats."""
        return user_id in self._settings.access.allowed_user_ids or self.is_admin(user_id)

    def is_allowed_chat(self, chat_id: int) -> bool:
        """Return ``True`` if *chat_id* is in the allowed-chat list."""
        return chat_id in self._settings.access.allowed_chat_ids

    def is_direct_request(self, message: Message) -> bool:
        """Return ``True`` if the message is addressed to the bot.

        A message is considered a direct request when:
        * It is a reply to one of the bot's messages, **or**
        * It contains an ``@bot_username`` mention.
        """
        return self._is_direct_request(message)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check(self, update: Update) -> bool:
        """Return ``True`` if the update should be handled."""
        message: Message | None = update.message
        if message is None:
            logger.debug("No message in update")
            return False

        user_id = message.from_user.id if message.from_user else 0
        chat_type = message.chat.type
        chat_id = message.chat.id

        logger.debug(
            f"Access check: chat_type={chat_type}, chat_id={chat_id}, "
            f"user_id={user_id}, text={message.text[:30] if message.text else 'N/A'}..."
        )

        # Private chat – just check user
        if chat_type == "private":
            allowed = self.is_allowed_user(user_id)
            if not allowed:
                logger.warning(
                    f"Rejected private message from user {user_id} (not in allowed list)"
                )
            else:
                logger.info(f"Accepted private message from user {user_id}")
            return allowed

        # Group / supergroup – check chat + direct mention
        if chat_type in ("group", "supergroup"):
            if not self.is_allowed_chat(chat_id):
                logger.warning(
                    f"Rejected message from disallowed chat {chat_id}. "
                    f"Allowed chats: {self._settings.access.allowed_chat_ids}"
                )
                return False

            logger.debug(f"Chat {chat_id} is in allowed list, checking direct request...")

            if not self._is_direct_request(message):
                logger.info(
                    f"Rejected message in chat {chat_id} (not a direct request to bot). "
                    f"Text: {message.text[:50] if message.text else 'N/A'}..."
                )
                return False

            logger.info(f"✓ Accepted message in group chat {chat_id} from user {user_id}")
            return True

        logger.debug(f"Unknown chat type: {chat_type}")
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_direct_request(self, message: Message) -> bool:
        """Return ``True`` if the message is addressed to the bot.

        A message is considered a direct request when:
        * It is a reply to one of the bot's messages, **or**
        * It contains an ``@bot_username`` mention.
        """
        bot_username = self._settings.bot.username.lower()

        entities_info = (
            [(e.type, e.offset, e.length) for e in message.entities]
            if message.entities
            else "None"
        )
        logger.debug(
            f"Checking direct request: chat_id={message.chat.id}, "
            f"text={message.text[:50] if message.text else 'N/A'}..., "
            f"entities={entities_info}"
        )

        # Reply to bot - check if reply_to_message is from a bot
        if message.reply_to_message and message.reply_to_message.from_user:
            # Check if the replied message is from a bot
            if message.reply_to_message.from_user.is_bot:
                replied_username = message.reply_to_message.from_user.username
                logger.debug(
                    f"Reply to bot detected: replied_username="
                    f"{replied_username}, bot_username={bot_username}"
                )
                if replied_username and replied_username.lower() == bot_username:
                    logger.info("Direct request detected: reply to bot")
                    return True

        # @mention in text - check both entities and raw text
        if message.text:
            # Check entities first
            if message.entities:
                for entity in message.entities:
                    if entity.type == "mention":
                        mention = message.text[entity.offset : entity.offset + entity.length]
                        logger.debug(f"Found mention entity: {mention}")
                        if mention.lower() == f"@{bot_username}":
                            logger.info(f"Direct request detected: mention via entity {mention}")
                            return True

            # Also check raw text for @bot_username (case when entity is not created)
            mention_string = f"@{bot_username}"
            if mention_string in message.text.lower():
                logger.info(f"Direct request detected: mention in text {mention_string}")
                return True

        logger.debug("No direct request detected (no mention or reply to bot)")
        return False
