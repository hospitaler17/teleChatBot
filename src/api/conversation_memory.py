"""Conversation memory management for maintaining chat history."""

from __future__ import annotations

import logging
from collections import defaultdict

from mistralai.models import AssistantMessage, UserMessage

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Stores conversation history per user/chat to provide context.

    In private chats, history is stored per user_id.
    In group chats, history is stored per chat_id (shared context).
    """

    def __init__(self, max_history: int = 10):
        """
        Initialize conversation memory.

        Args:
            max_history: Maximum number of message pairs to keep (default: 10)
        """
        self.max_history = max_history
        # Format: {context_id: [{"role": "user", "content": "..."},
        #                        {"role": "assistant", "content": "..."}]}
        # context_id can be user_id (private chats) or chat_id (groups)
        self.history: dict[int, list] = defaultdict(list)
        logger.info(f"Conversation memory initialized with max_history={max_history}")

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups
            role: "user" or "assistant"
            content: Message content
        """
        self.history[user_id].append({"role": role, "content": content})

        # Keep only last max_history messages
        if len(self.history[user_id]) > self.max_history * 2:  # *2 because pairs of user+assistant
            self.history[user_id] = self.history[user_id][-(self.max_history * 2) :]

        logger.debug(
            f"Added {role} message for context {user_id}, "
            f"history size: {len(self.history[user_id])}"
        )

    def get_history(self, user_id: int) -> list:
        """
        Get conversation history for a context.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups

        Returns:
            List of messages with role and content
        """
        return self.history.get(user_id, [])

    def get_messages_for_api(self, user_id: int) -> list:
        """
        Convert history to Mistral API message format.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups

        Returns:
            List of UserMessage and AssistantMessage objects
        """
        messages = []
        for msg in self.history.get(user_id, []):
            if msg["role"] == "user":
                messages.append(UserMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AssistantMessage(content=msg["content"]))

        return messages

    def clear_history(self, user_id: int) -> None:
        """
        Clear conversation history for a context.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups
        """
        if user_id in self.history:
            del self.history[user_id]
            logger.info(f"Cleared history for context {user_id}")

    def get_stats(self, user_id: int) -> dict:
        """
        Get statistics about conversation history.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups

        Returns:
            Dictionary with stats
        """
        messages = self.history.get(user_id, [])
        return {
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant"),
        }
