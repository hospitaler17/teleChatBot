"""Entry point for teleChatBot."""

from __future__ import annotations

import asyncio
import logging
import sys
import time

from telegram.error import NetworkError, TimedOut

from src.bot.bot import create_bot
from src.cli.cli_chat import run_cli
from src.config.settings import AppSettings

# Exponential backoff settings for Telegram polling restart after network errors.
_POLLING_BACKOFF_BASE = 1.0   # initial retry delay (seconds)
_POLLING_BACKOFF_MAX = 60.0   # maximum retry delay (seconds)


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
        try:
            asyncio.run(run_cli(settings))
        except KeyboardInterrupt:
            logger.info("CLI interrupted by user (Ctrl+C). Shutting down.")
            sys.exit(0)
        except Exception:
            logger.exception("Unhandled exception in CLI mode")
            sys.exit(1)
    else:
        # Telegram mode requires bot token
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not set")
            sys.exit(1)

        logger.info("Starting teleChatBot in Telegram mode...")
        _run_polling_with_backoff(settings, logger)


def _run_polling_with_backoff(settings: AppSettings, logger: logging.Logger) -> None:
    """Run bot polling, restarting with exponential backoff on network errors.

    ``app.run_polling()`` is a *synchronous* blocking call that internally starts
    its own event loop via ``asyncio.run()``.  Between restarts (after the loop
    exits) we are in a plain synchronous context with no active event loop, so
    ``time.sleep()`` is correct here — ``asyncio.sleep()`` cannot be awaited
    outside an event loop.
    """
    delay = _POLLING_BACKOFF_BASE
    while True:
        app = create_bot(settings)
        try:
            app.run_polling()
            # Clean exit (e.g. KeyboardInterrupt propagated as SystemExit) — stop looping.
            return
        except KeyboardInterrupt:
            logger.info("Polling interrupted by user (Ctrl+C). Shutting down.")
            return
        except (NetworkError, TimedOut) as exc:
            logger.warning(
                "Network error during polling (%s: %s). "
                "Restarting in %.1f s (exponential backoff).",
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, _POLLING_BACKOFF_MAX)
        except Exception:
            logger.exception("Unhandled exception while polling")
            sys.exit(1)


if __name__ == "__main__":
    main()
