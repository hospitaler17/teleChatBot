"""Command-line interface for testing Mistral API integration.

Useful for debugging system prompts and testing model responses without Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

from src.api.mistral_client import MistralClient
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class CLIChat:
    """Interactive command-line chat interface."""

    def __init__(self, settings: AppSettings):
        """Initialize CLI chat with Mistral client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.client = MistralClient(settings)
        self.user_id = 1  # Fixed user ID for CLI sessions
        self.running = False

    def print_banner(self) -> None:
        """Print welcome banner with configuration info."""
        print("=" * 70)
        print("  teleChatBot - CLI Mode")
        print("=" * 70)
        print(f"  Model: {self.settings.mistral.model}")
        print(f"  Temperature: {self.settings.mistral.temperature}")
        print(f"  Max tokens: {self.settings.mistral.max_tokens}")
        web_search_status = 'enabled' if self.settings.mistral.enable_web_search else 'disabled'
        print(f"  Web search: {web_search_status}")
        print(f"  History size: {self.settings.mistral.conversation_history_size} messages")
        if self.settings.mistral.system_prompt:
            print(f"  System prompt: {self.settings.mistral.system_prompt[:50]}...")
        print("-" * 70)
        print("  Commands:")
        print("    /exit, /quit  - Exit CLI mode")
        print("    /clear        - Clear conversation history")
        print("    /stats        - Show conversation statistics")
        print("    /help         - Show this help")
        print("=" * 70)
        print()

    def print_help(self) -> None:
        """Print help message."""
        print("\n" + "=" * 70)
        print("  Available Commands:")
        print("=" * 70)
        print("  /exit, /quit  - Exit CLI mode")
        print("  /clear        - Clear conversation history")
        print("  /stats        - Show conversation statistics")
        print("  /help         - Show this help")
        print("=" * 70 + "\n")

    def print_stats(self) -> None:
        """Print conversation statistics."""
        stats = self.client._memory.get_stats(self.user_id)
        print("\n" + "=" * 70)
        print("  Conversation Statistics:")
        print("=" * 70)
        print(f"  Total messages: {stats['total_messages']}")
        print(f"  User messages: {stats['user_messages']}")
        print(f"  Assistant messages: {stats['assistant_messages']}")
        print("=" * 70 + "\n")

    async def handle_message(self, user_input: str) -> tuple[Optional[str], Optional[dict]] | None:
        """Process user message and get response.

        Args:
            user_input: User's input message

        Returns:
            Tuple of (response_text, metadata) where metadata contains model and token info,
            or None if command was handled
        """
        # Handle commands
        if user_input.lower() in ["/exit", "/quit"]:
            self.running = False
            return None

        if user_input.lower() == "/clear":
            self.client._memory.clear_history(self.user_id)
            print("\n✓ Conversation history cleared.\n")
            return None

        if user_input.lower() == "/stats":
            self.print_stats()
            return None

        if user_input.lower() == "/help":
            self.print_help()
            return None

        # Process normal message
        try:
            # Add user message to history
            self.client._memory.add_message(self.user_id, "user", user_input)

            # Generate response
            response = await self.client.generate(user_input, user_id=self.user_id)

            # Extract content and metadata
            response_text = response.content
            metadata = {
                "model": response.model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            }

            # Add assistant response to history
            self.client._memory.add_message(self.user_id, "assistant", response_text)

            return response_text, metadata

        except Exception as e:
            logger.exception("Error generating response")
            return f"❌ Error: {str(e)}", None

    async def run(self) -> None:
        """Run the interactive CLI chat loop."""
        self.print_banner()
        self.running = True

        print("Type your message and press Enter. Use /help for commands.\n")

        while self.running:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()

                if not user_input:
                    continue

                # Handle message and get response
                result = await self.handle_message(user_input)

                if result is None:
                    continue

                if isinstance(result, tuple):
                    response, metadata = result
                    if response:
                        print(f"\n🤖 Bot: {response}")
                        if metadata:
                            # Format token statistics in one line with emoji
                            tokens_info = (
                                f"  ⚡ {metadata['model']} "
                                f"| input: {metadata['input_tokens']} "
                                f"| output: {metadata['output_tokens']} "
                                f"| total: {metadata['total_tokens']}"
                            )
                            print(tokens_info)
                else:
                    # Fallback for string responses (shouldn't happen now)
                    if result:
                        print(f"\n🤖 Bot: {result}")

            except KeyboardInterrupt:
                print("\n\n👋 Exiting CLI mode...")
                break
            except EOFError:
                print("\n\n👋 Exiting CLI mode...")
                break
            except Exception as e:
                logger.exception("Error in CLI loop")
                print(f"\n❌ Error: {str(e)}")

        print("\nGoodbye!\n")


async def run_cli(settings: AppSettings) -> None:
    """Run the CLI chat interface.

    Args:
        settings: Application settings
    """
    chat = CLIChat(settings)
    await chat.run()


def main() -> None:
    """Entry point for CLI mode when run directly."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = AppSettings.load()

    if not settings.mistral_api_key:
        logger.error("MISTRAL_API_KEY is not set")
        sys.exit(1)

    logger.info("Starting CLI mode")
    asyncio.run(run_cli(settings))


if __name__ == "__main__":
    main()
