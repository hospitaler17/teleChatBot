"""Bot application assembly — wires handlers to the Telegram dispatcher."""

from __future__ import annotations

import logging

from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import (
    Application,
    ContextTypes,
    filters,
)
from telegram.ext import (
    CommandHandler as TGCommandHandler,
)
from telegram.ext import (
    MessageHandler as TGMessageHandler,
)

from src.api.provider_router import ProviderRouter
from src.bot.filters.access_filter import AccessFilter
from src.bot.handlers.admin_handler import AdminHandler
from src.bot.handlers.command_handler import CommandHandler
from src.bot.handlers.message_handler import MessageHandler
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler — logs Telegram API errors without crashing the bot.

    Transient network errors (NetworkError, TimedOut) are logged at WARNING level
    so that operators can monitor connectivity issues without flooding logs.
    All other errors are logged at ERROR level with a full traceback.
    """
    error = context.error

    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning(
            "Transient Telegram API error (will recover automatically): %s: %s",
            type(error).__name__,
            error,
        )
    elif isinstance(error, TelegramError):
        logger.error(
            "Telegram API error: %s: %s",
            type(error).__name__,
            error,
            exc_info=error,
        )
    else:
        logger.exception(
            "Unexpected error while processing update %s",
            update,
            exc_info=error,
        )


def create_bot(settings: AppSettings) -> Application:
    """Build and return a fully configured ``Application``."""
    router = ProviderRouter(settings)
    mistral_client = router.mistral
    access_filter = AccessFilter(settings)

    # Handlers
    cmd = CommandHandler(access_filter, settings.bot.username)
    msg = MessageHandler(settings, mistral_client, access_filter, provider_router=router)
    admin = AdminHandler(settings, access_filter)

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Global error handler — recovers from transient Telegram API / network errors
    app.add_error_handler(_error_handler)

    # Basic commands
    app.add_handler(TGCommandHandler("start", cmd.start))
    app.add_handler(TGCommandHandler("help", cmd.help))

    # Admin commands
    app.add_handler(TGCommandHandler("admin_add_user", admin.add_user))
    app.add_handler(TGCommandHandler("admin_remove_user", admin.remove_user))
    app.add_handler(TGCommandHandler("admin_add_chat", admin.add_chat))
    app.add_handler(TGCommandHandler("admin_remove_chat", admin.remove_chat))
    app.add_handler(TGCommandHandler("admin_list", admin.list_access))
    app.add_handler(TGCommandHandler("admin_reactions_on", admin.reactions_on))
    app.add_handler(TGCommandHandler("admin_reactions_off", admin.reactions_off))
    app.add_handler(TGCommandHandler("admin_reactions_status", admin.reactions_status))
    app.add_handler(TGCommandHandler("admin_date_on", admin.date_on))
    app.add_handler(TGCommandHandler("admin_date_off", admin.date_off))
    app.add_handler(TGCommandHandler("admin_date_status", admin.date_status))
    app.add_handler(TGCommandHandler("admin_reasoning_on", admin.reasoning_on))
    app.add_handler(TGCommandHandler("admin_reasoning_off", admin.reasoning_off))
    app.add_handler(TGCommandHandler("admin_reasoning_status", admin.reasoning_status))

    # Text messages and other message types (lowest priority)
    # Handles: text, forwarded messages, replies, media with captions
    # Use ~filters.COMMAND to exclude commands, but accept all other message types
    message_filter = ~filters.COMMAND
    app.add_handler(TGMessageHandler(message_filter, msg.handle))

    logger.info("Bot application created")
    return app
