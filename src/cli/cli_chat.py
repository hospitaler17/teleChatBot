"""Command-line interface for testing Mistral API integration.

Useful for debugging system prompts and testing model responses without Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

from src.api.admin_commands import AdminCommandService
from src.api.provider_router import ProviderRouter
from src.bot.filters.access_filter import AccessFilter
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
        self._router = ProviderRouter(settings)
        self.client = self._router.mistral
        # Fixed user ID for CLI sessions (reserved for local testing)
        self.user_id = 1
        # Ensure the CLI user is present in the admin list so admin commands work in CLI mode
        admin_user_ids = list(settings.admin.user_ids or [])
        if self.user_id not in admin_user_ids:
            admin_user_ids.append(self.user_id)
            settings.admin.user_ids = admin_user_ids
        self.running = False
        # Initialize admin commands service
        access_filter = AccessFilter(settings)
        self.admin_commands = AdminCommandService(settings, access_filter)
        # Detect whether the console supports emoji printing to avoid UnicodeEncodeError
        self.use_emoji = True
        try:
            enc = sys.stdout.encoding or "utf-8"
            "👤".encode(enc)
        except Exception:
            self.use_emoji = False

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
        streaming_status = 'enabled' if self.settings.bot.enable_streaming else 'disabled'
        print(f"  Streaming: {streaming_status}")
        if self.settings.mistral.system_prompt:
            print(f"  System prompt: {self.settings.mistral.system_prompt[:50]}...")
        print("-" * 70)
        print("  Chat Commands:")
        print("    /exit, /quit  - Exit CLI mode")
        print("    /clear        - Clear conversation history")
        print("    /stats        - Show conversation statistics")
        print("    /help         - Show this help")
        print("  Admin Commands:")
        print("    /admin_list   - Show access lists and reactions status")
        print("    /admin_reactions_on  - Enable automatic reactions")
        print("    /admin_reactions_off - Disable automatic reactions")
        print("    /admin_reactions_status - Show reactions configuration")
        print("    /admin_reasoning_on  - Enable chain-of-thought reasoning mode")
        print("    /admin_reasoning_off - Disable chain-of-thought reasoning mode")
        print("    /admin_reasoning_status - Show reasoning mode configuration")
        print("=" * 70)
        print()
        # Flush stdout to ensure banner is visible immediately, especially on Windows
        sys.stdout.flush()

    def print_help(self) -> None:
        """Print help message."""
        print("\n" + "=" * 70)
        print("  Available Commands:")
        print("=" * 70)
        print("  Chat Commands:")
        print("    /exit, /quit  - Exit CLI mode")
        print("    /clear        - Clear conversation history")
        print("    /stats        - Show conversation statistics")
        print("    /help         - Show this help")
        print("  Admin Commands:")
        print("    /admin_list   - Show access lists and reactions status")
        print("    /admin_reactions_on  - Enable automatic reactions")
        print("    /admin_reactions_off - Disable automatic reactions")
        print("    /admin_reactions_status - Show reactions configuration")
        print("    /admin_reasoning_on  - Enable chain-of-thought reasoning mode")
        print("    /admin_reasoning_off - Disable chain-of-thought reasoning mode")
        print("    /admin_reasoning_status - Show reasoning mode configuration")
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
        # Handle chat commands
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

        # Handle admin commands
        if user_input.lower() == "/admin_list":
            _success, message = self.admin_commands.list_access(self.user_id)
            # Remove markdown formatting for CLI display
            message = message.replace("*", "").replace("`", "")
            print(f"\n{message}\n")
            return None

        if user_input.lower() == "/admin_reactions_on":
            _success, message = self.admin_commands.reactions_on(self.user_id)
            print(f"\n{message}\n")
            return None

        if user_input.lower() == "/admin_reactions_off":
            _success, message = self.admin_commands.reactions_off(self.user_id)
            print(f"\n{message}\n")
            return None

        if user_input.lower() == "/admin_reactions_status":
            _success, message = self.admin_commands.reactions_status(self.user_id)
            # Remove markdown formatting for CLI display
            message = message.replace("*", "").replace("`", "")
            print(f"\n{message}\n")
            return None

        if user_input.lower() == "/admin_reasoning_on":
            _success, message = self.admin_commands.reasoning_on(self.user_id)
            print(f"\n{message}\n")
            return None

        if user_input.lower() == "/admin_reasoning_off":
            _success, message = self.admin_commands.reasoning_off(self.user_id)
            print(f"\n{message}\n")
            return None

        if user_input.lower() == "/admin_reasoning_status":
            _success, message = self.admin_commands.reasoning_status(self.user_id)
            # Remove markdown formatting for CLI display
            message = message.replace("*", "").replace("`", "")
            print(f"\n{message}\n")
            return None

        # Process normal message
        try:
            # Add user message to history
            self.client._memory.add_message(self.user_id, "user", user_input)

            # Determine and display status message
            status_messages = self.settings.status_messages
            if (
                self.client._web_search
                and self.client._should_use_web_search(user_input)
            ):
                status_text = status_messages.searching
            else:
                status_text = status_messages.thinking
            print(f"\n{status_text}")

            # Check if streaming is enabled
            if self.settings.bot.enable_streaming:
                # Use streaming mode
                bot_label = "\n🤖 Bot: " if self.use_emoji else "\nBot: "
                print(bot_label, end='', flush=True)
                accumulated_content = ""

                async for chunk_content, full_content, is_final, _urls in (
                    self._router.generate_stream(
                        user_input, user_id=self.user_id
                    )
                ):
                    accumulated_content = full_content
                    if chunk_content:
                        # Print new content as it arrives
                        print(chunk_content, end='', flush=True)

                print()  # New line after streaming completes

                # Add assistant response to history
                self.client._memory.add_message(self.user_id, "assistant", accumulated_content)

                # Return None for metadata since we don't have it in final chunk yet
                # We could enhance this to extract metadata from the final chunk
                return accumulated_content, None
            else:
                # Use non-streaming mode (original behavior)
                response = await self._router.generate(user_input, user_id=self.user_id)

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
        sys.stdout.flush()

        while self.running:
            try:
                # Get user input
                prompt = "\n👤 You: " if self.use_emoji else "\nYou: "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Handle message and get response
                result = await self.handle_message(user_input)

                if result is None:
                    continue

                if isinstance(result, tuple):
                    response, metadata = result
                    # Only show metadata if we have it (non-streaming mode)
                    if response and metadata:
                        # Response already printed in streaming mode
                        if not self.settings.bot.enable_streaming:
                            print(f"\n🤖 Bot: {response}")
                        # Format token statistics in one line with emoji
                        tokens_info = (
                            f"  ⚡ {metadata['model']} "
                            f"| input: {metadata['input_tokens']} "
                            f"| output: {metadata['output_tokens']} "
                            f"| total: {metadata['total_tokens']}"
                        )
                        print(tokens_info)
                    elif response and not metadata:
                        # Streaming mode - response already printed, no metadata
                        pass
                else:
                    # Fallback for string responses (shouldn't happen now)
                    if result:
                        print(f"\n🤖 Bot: {result}")

            except KeyboardInterrupt:
                bye = "\n\n👋 Exiting CLI mode..." if self.use_emoji else "\n\nExiting CLI mode..."
                print(bye)
                break
            except EOFError:
                bye = "\n\n👋 Exiting CLI mode..." if self.use_emoji else "\n\nExiting CLI mode..."
                print(bye)
                break
            except Exception as e:
                logger.exception("Error in CLI loop")
                err_label = "\n❌ Error: " if self.use_emoji else "\nError: "
                print(f"{err_label}{str(e)}")

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
