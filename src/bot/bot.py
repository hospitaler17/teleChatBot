"""Bot application assembly — wires handlers to the Telegram dispatcher."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    filters,
)
from telegram.ext import (
    CommandHandler as TGCommandHandler,
)
from telegram.ext import (
    MessageHandler as TGMessageHandler,
)

from src.api.mistral_client import MistralClient
from src.bot.filters.access_filter import AccessFilter
from src.bot.handlers.admin_handler import AdminHandler
from src.bot.handlers.command_handler import CommandHandler
from src.bot.handlers.message_handler import MessageHandler
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


def create_bot(settings: AppSettings) -> Application:
    """Build and return a fully configured :class:`Application`."""
    mistral_client = MistralClient(settings)
    access_filter = AccessFilter(settings)

    # Handlers
    cmd = CommandHandler(access_filter, settings.bot.username)
    msg = MessageHandler(settings, mistral_client, access_filter)
    admin = AdminHandler(settings, access_filter)

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Basic commands
    app.add_handler(TGCommandHandler("start", cmd.start))
    app.add_handler(TGCommandHandler("help", cmd.help))

    # Admin commands
    app.add_handler(TGCommandHandler("admin_add_user", admin.add_user))
    app.add_handler(TGCommandHandler("admin_remove_user", admin.remove_user))
    app.add_handler(TGCommandHandler("admin_add_chat", admin.add_chat))
    app.add_handler(TGCommandHandler("admin_remove_chat", admin.remove_chat))
    app.add_handler(TGCommandHandler("admin_list", admin.list_access))

    # Text messages and other message types (lowest priority)
    # Handles: text, forwarded messages, replies, media with captions
    # Use ~filters.COMMAND to exclude commands, but accept all other message types
    message_filter = ~filters.COMMAND
    app.add_handler(TGMessageHandler(message_filter, msg.handle))

    logger.info("Bot application created")
    return app
