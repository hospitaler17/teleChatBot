"""Entry point for teleChatBot."""

from __future__ import annotations

import asyncio
import logging
import sys

from src.bot.bot import create_bot
from src.cli.cli_chat import run_cli
from src.config.settings import AppSettings


def main() -> None:
    """Load configuration, create the bot, and start polling or CLI mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    settings = AppSettings.load()

    # Check for required API key
    if not settings.mistral_api_key:
        logger.error("MISTRAL_API_KEY is not set")
        sys.exit(1)

    # Check if CLI mode is enabled
    if settings.bot.cli_mode:
        logger.info("Starting teleChatBot in CLI mode...")
        asyncio.run(run_cli(settings))
    else:
        # Telegram mode requires bot token
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not set")
            sys.exit(1)

        logger.info("Starting teleChatBot in Telegram mode...")
        app = create_bot(settings)
        app.run_polling()


if __name__ == "__main__":
    main()
