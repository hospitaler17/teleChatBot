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
        self._settings = settings

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_admin(self, user_id: int) -> bool:
        """Return ``True`` if *user_id* is in the admin list."""
        return user_id in self._settings.admin.user_ids

    def is_allowed_user(self, user_id: int) -> bool:
        """Return ``True`` if *user_id* is allowed in private chats."""
        return (
            user_id in self._settings.access.allowed_user_ids
            or self.is_admin(user_id)
        )

    def is_allowed_chat(self, chat_id: int) -> bool:
        """Return ``True`` if *chat_id* is in the allowed-chat list."""
        return chat_id in self._settings.access.allowed_chat_ids

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check(self, update: Update) -> bool:
        """Return ``True`` if the update should be handled."""
        message: Message | None = update.message
        if message is None:
            return False

        user_id = message.from_user.id if message.from_user else 0
        chat_type = message.chat.type

        # Private chat – just check user
        if chat_type == "private":
            allowed = self.is_allowed_user(user_id)
            if not allowed:
                logger.debug("Rejected private message from user %s", user_id)
            return allowed

        # Group / supergroup – check chat + direct mention
        if chat_type in ("group", "supergroup"):
            if not self.is_allowed_chat(message.chat.id):
                logger.debug("Rejected message from chat %s", message.chat.id)
                return False
            if not self._is_direct_request(message):
                return False
            return True

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

        # Reply to bot
        if message.reply_to_message and message.reply_to_message.from_user:
            if message.reply_to_message.from_user.username:
                if message.reply_to_message.from_user.username.lower() == bot_username:
                    return True

        # @mention in text
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention" and message.text:
                    mention = message.text[entity.offset : entity.offset + entity.length]
                    if mention.lower() == f"@{bot_username}":
                        return True

        return False
