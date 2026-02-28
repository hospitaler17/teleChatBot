"""Conversation memory management for maintaining chat history.

Uses SQLite for persistent storage of conversation history.
The database is created automatically on first use.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from mistralai.models import AssistantMessage, UserMessage

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "conversation_history.db"


class ConversationMemory:
    """Stores conversation history per user/chat in a SQLite database.

    In private chats, history is stored per user_id.
    In group chats, history is stored per chat_id (shared context).
    The database file is created automatically if it does not exist.
    """

    def __init__(self, max_history: int = 10, db_path: str | Path | None = None):
        """
        Initialize conversation memory with SQLite backend.

        Args:
            max_history: Maximum number of message pairs to keep (default: 10)
            db_path: Path to the SQLite database file.
                     Use ":memory:" for an in-memory database (useful for tests).
                     Defaults to ``data/conversation_history.db`` in the project root.
        """
        self.max_history = max_history

        if db_path is None:
            db_path = DEFAULT_DB_PATH

        self._db_path = str(db_path)

        # Create parent directory if using a file-based database
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()
        self._create_tables()
        logger.info(
            f"Conversation memory initialized with max_history={max_history}, "
            f"db_path={self._db_path}"
        )

    def _create_tables(self) -> None:
        """Create database tables if they do not exist."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages (user_id)"
        )
        self._conn.commit()

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups
            role: "user" or "assistant"
            content: Message content
        """
        self._conn.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        self._conn.commit()

        # Keep only last max_history * 2 messages (pairs of user+assistant)
        self._trim_history(user_id)

        count = self._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        logger.debug(
            f"Added {role} message for context {user_id}, history size: {count}"
        )

    def _trim_history(self, user_id: int) -> None:
        """Remove oldest messages when history exceeds the limit.

        Args:
            user_id: Context ID to trim history for
        """
        limit = self.max_history * 2  # *2 because pairs of user+assistant
        count = self._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        if count > limit:
            # Delete the oldest messages, keeping only the most recent `limit`
            self._conn.execute(
                """
                DELETE FROM messages
                WHERE user_id = ? AND id NOT IN (
                    SELECT id FROM messages
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (user_id, user_id, limit),
            )
            self._conn.commit()

    def add_system_context(self, user_id: int, context: str) -> None:
        """
        Add a system context message (not visible to user, only to model).

        Useful for providing background information like current date,
        search results, or other metadata that should inform the model
        but not appear in the user-facing conversation.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups
            context: Context content to add
        """
        self._conn.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, "system", context),
        )
        self._conn.commit()
        logger.debug(f"Added system context for user {user_id}: {context[:100]}...")

    def get_history(self, user_id: int) -> list:
        """
        Get conversation history for a context.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups

        Returns:
            List of messages with role and content
        """
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        return [{"role": role, "content": content} for role, content in rows]

    def get_messages_for_api(self, user_id: int) -> list:
        """
        Convert history to Mistral API message format.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups

        Returns:
            List of UserMessage and AssistantMessage objects
        """
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()

        messages = []
        for role, content in rows:
            if role == "user":
                messages.append(UserMessage(content=content))
            elif role == "assistant":
                messages.append(AssistantMessage(content=content))
            # Note: system context messages are handled separately in mistral_client.py

        return messages

    def clear_history(self, user_id: int) -> None:
        """
        Clear conversation history for a context.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups
        """
        deleted = self._conn.execute(
            "DELETE FROM messages WHERE user_id = ?", (user_id,)
        ).rowcount
        self._conn.commit()
        if deleted:
            logger.info(f"Cleared history for context {user_id}")

    def get_stats(self, user_id: int) -> dict:
        """
        Get statistics about conversation history.

        Args:
            user_id: Context ID - user_id for private chats, chat_id for groups

        Returns:
            Dictionary with stats
        """
        rows = self._conn.execute(
            "SELECT role, COUNT(*) FROM messages WHERE user_id = ? GROUP BY role",
            (user_id,),
        ).fetchall()

        stats: dict[str, int] = {role: count for role, count in rows}
        return {
            "total_messages": sum(stats.values()),
            "user_messages": stats.get("user", 0),
            "assistant_messages": stats.get("assistant", 0),
        }

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("Conversation memory database connection closed")
