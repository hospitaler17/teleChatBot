"""Persistent storage of bot settings, users and groups using SQLite.

The same SQLite file that holds conversation history is reused (additional
tables are simply added to it).  On first use the tables are empty; call
:meth:`initialize_from_config` to seed them from the YAML configuration.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "conversation_history.db"
)


class BotDatabase:
    """Manages bot settings, allowed users and allowed groups in SQLite.

    Tables
    ------
    ``settings``
        Key/value pairs for runtime toggles:
        ``reactions_enabled``, ``web_search_enabled``, ``reasoning_mode_enabled``.
    ``users``
        Allowed (non-admin) user IDs for private-chat access.
    ``groups``
        Allowed group/supergroup chat IDs.

    On first use (all tables empty) call :meth:`initialize_from_config` to
    import data from the YAML configuration.  Afterwards the DB is the
    authoritative source and is loaded at startup via
    :meth:`AppSettings.load`.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Open (or create) the SQLite database and create tables.

        Args:
            db_path: Path to the SQLite file.  Pass ``":memory:"`` for an
                in-memory database (useful in tests).  Defaults to the shared
                ``data/conversation_history.db`` file.
        """
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()
        self._create_tables()
        logger.info("BotDatabase opened: %s", self._db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create the settings, users and groups tables if they do not exist."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return ``True`` when all three managed tables contain no rows."""
        counts = [
            self._conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0],
            self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            self._conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
        ]
        return all(c == 0 for c in counts)

    def initialize_from_config(
        self,
        user_ids: list[int],
        chat_ids: list[int],
        reactions_enabled: bool,
        web_search_enabled: bool,
        reasoning_mode_enabled: bool,
    ) -> None:
        """Seed the database from YAML config values (called when the DB is empty).

        Args:
            user_ids: Allowed user IDs from ``allowed_users.yaml``.
            chat_ids: Allowed chat IDs from ``allowed_users.yaml``.
            reactions_enabled: Initial value for the reactions toggle.
            web_search_enabled: Initial value for the web-search toggle.
            reasoning_mode_enabled: Initial value for the reasoning-mode toggle.
        """
        with self._lock:
            for uid in user_ids:
                self._conn.execute(
                    "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,)
                )
            for cid in chat_ids:
                self._conn.execute(
                    "INSERT OR IGNORE INTO groups (chat_id) VALUES (?)", (cid,)
                )
            for key, value in [
                ("reactions_enabled", reactions_enabled),
                ("web_search_enabled", web_search_enabled),
                ("reasoning_mode_enabled", reasoning_mode_enabled),
            ]:
                self._conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, int(value)),
                )
            self._conn.commit()
        logger.info("Bot database seeded from YAML config")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def get_settings(self) -> dict[str, bool]:
        """Return all stored settings as ``{key: bool}``."""
        rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        return {key: bool(value) for key, value in rows}

    def set_setting(self, key: str, value: bool) -> None:
        """Insert or update a single setting.

        Args:
            key: Setting name (e.g. ``"reactions_enabled"``).
            value: New boolean value.
        """
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, int(value)),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_users(self) -> list[int]:
        """Return the list of allowed user IDs."""
        rows = self._conn.execute("SELECT user_id FROM users").fetchall()
        return [row[0] for row in rows]

    def add_user(self, user_id: int) -> bool:
        """Add *user_id* to the allowed list.

        Args:
            user_id: Telegram user ID to add.

        Returns:
            ``True`` if the row was newly inserted, ``False`` if it already existed.
        """
        with self._lock:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def remove_user(self, user_id: int) -> bool:
        """Remove *user_id* from the allowed list.

        Args:
            user_id: Telegram user ID to remove.

        Returns:
            ``True`` if the row existed and was deleted, ``False`` otherwise.
        """
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM users WHERE user_id = ?", (user_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Groups / chats
    # ------------------------------------------------------------------

    def get_chats(self) -> list[int]:
        """Return the list of allowed chat IDs."""
        rows = self._conn.execute("SELECT chat_id FROM groups").fetchall()
        return [row[0] for row in rows]

    def add_chat(self, chat_id: int) -> bool:
        """Add *chat_id* to the allowed list.

        Args:
            chat_id: Telegram chat ID to add.

        Returns:
            ``True`` if the row was newly inserted, ``False`` if it already existed.
        """
        with self._lock:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO groups (chat_id) VALUES (?)", (chat_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def remove_chat(self, chat_id: int) -> bool:
        """Remove *chat_id* from the allowed list.

        Args:
            chat_id: Telegram chat ID to remove.

        Returns:
            ``True`` if the row existed and was deleted, ``False`` otherwise.
        """
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM groups WHERE chat_id = ?", (chat_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Full sync
    # ------------------------------------------------------------------

    def sync_from_settings(
        self,
        user_ids: list[int],
        chat_ids: list[int],
        reactions_enabled: bool,
        web_search_enabled: bool,
        reasoning_mode_enabled: bool,
    ) -> None:
        """Replace all rows with the current in-memory state.

        Called by :meth:`AppSettings.save_access` so that every admin-command
        change is persisted to the DB in addition to the YAML file.

        Args:
            user_ids: Current allowed user IDs.
            chat_ids: Current allowed chat IDs.
            reactions_enabled: Current reactions toggle value.
            web_search_enabled: Current web-search toggle value.
            reasoning_mode_enabled: Current reasoning-mode toggle value.
        """
        with self._lock:
            self._conn.execute("DELETE FROM users")
            for uid in user_ids:
                self._conn.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
            self._conn.execute("DELETE FROM groups")
            for cid in chat_ids:
                self._conn.execute("INSERT INTO groups (chat_id) VALUES (?)", (cid,))
            for key, value in [
                ("reactions_enabled", reactions_enabled),
                ("web_search_enabled", web_search_enabled),
                ("reasoning_mode_enabled", reasoning_mode_enabled),
            ]:
                self._conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, int(value)),
                )
            self._conn.commit()
        logger.info("Bot database synced from in-memory settings")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
        logger.info("BotDatabase connection closed")
