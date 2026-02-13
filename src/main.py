"""Entry point for teleChatBot."""

from __future__ import annotations

import logging
import sys

from src.bot.bot import create_bot
from src.config.settings import AppSettings


def main() -> None:
    """Load configuration, create the bot, and start polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    settings = AppSettings.load()

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)
    if not settings.mistral_api_key:
        logger.error("MISTRAL_API_KEY is not set")
        sys.exit(1)

    logger.info("Starting teleChatBot…")
    app = create_bot(settings)
    app.run_polling()


if __name__ == "__main__":
    main()
