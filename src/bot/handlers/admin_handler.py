"""Admin-only Telegram commands for managing bot settings at runtime."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.api.admin_commands import AdminCommandService
from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class AdminHandler:
    """Provides ``/admin_*`` commands available only to admins.

    Supported commands
    ------------------
    /admin_add_user <user_id>     – add a user to the allowed list
    /admin_remove_user <user_id>  – remove a user from the allowed list
    /admin_add_chat <chat_id>     – add a chat to the allowed list
    /admin_remove_chat <chat_id>  – remove a chat from the allowed list
    /admin_list                   – show current allowed users and chats
    /admin_reactions_on           – enable automatic message reactions
    /admin_reactions_off          – disable automatic message reactions
    /admin_reactions_status       – show reactions status and configuration
    /admin_date_on                – enable always appending date to system prompt
    /admin_date_off               – disable always appending date to system prompt
    /admin_date_status            – show date appending status and configuration
    /admin_reasoning_on           – enable chain-of-thought reasoning mode
    /admin_reasoning_off          – disable chain-of-thought reasoning mode
    /admin_reasoning_status       – show reasoning mode status and configuration
    /admin_web_search_on          – enable web search
    /admin_web_search_off         – disable web search
    /admin_web_search_status      – show web search status
    /backup                       – create and send a backup archive
    """

    def __init__(self, settings: AppSettings, access_filter: AccessFilter) -> None:
        self._commands = AdminCommandService(settings, access_filter)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def add_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_add_user <user_id>"""
        admin_id = update.effective_user.id if update.effective_user else 0
        uid = self._parse_int_arg(context)
        if uid is None:
            await update.message.reply_text("Использование: /admin_add_user <user_id>")
            return
        _success, message = self._commands.add_user(uid, admin_id)
        await update.message.reply_text(message)

    async def remove_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_remove_user <user_id>"""
        admin_id = update.effective_user.id if update.effective_user else 0
        uid = self._parse_int_arg(context)
        if uid is None:
            await update.message.reply_text("Использование: /admin_remove_user <user_id>")
            return
        _success, message = self._commands.remove_user(uid, admin_id)
        await update.message.reply_text(message)

    async def add_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_add_chat <chat_id>"""
        admin_id = update.effective_user.id if update.effective_user else 0
        cid = self._parse_int_arg(context)
        if cid is None:
            await update.message.reply_text("Использование: /admin_add_chat <chat_id>")
            return
        _success, message = self._commands.add_chat(cid, admin_id)
        await update.message.reply_text(message)

    async def remove_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_remove_chat <chat_id>"""
        admin_id = update.effective_user.id if update.effective_user else 0
        cid = self._parse_int_arg(context)
        if cid is None:
            await update.message.reply_text("Использование: /admin_remove_chat <chat_id>")
            return
        _success, message = self._commands.remove_chat(cid, admin_id)
        await update.message.reply_text(message)

    async def list_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_list"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.list_access(admin_id)
        await update.message.reply_text(message, parse_mode="Markdown")

    async def reactions_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reactions_on"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.reactions_on(admin_id)
        await update.message.reply_text(message)

    async def reactions_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reactions_off"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.reactions_off(admin_id)
        await update.message.reply_text(message)

    async def reactions_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reactions_status"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.reactions_status(admin_id)
        await update.message.reply_text(message, parse_mode="Markdown")

    async def date_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_date_on"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.date_on(admin_id)
        await update.message.reply_text(message)

    async def date_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_date_off"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.date_off(admin_id)
        await update.message.reply_text(message)

    async def date_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_date_status"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.date_status(admin_id)
        await update.message.reply_text(message, parse_mode="Markdown")

    async def reasoning_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reasoning_on"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.reasoning_on(admin_id)
        await update.message.reply_text(message)

    async def reasoning_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reasoning_off"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.reasoning_off(admin_id)
        await update.message.reply_text(message)

    async def reasoning_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reasoning_status"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.reasoning_status(admin_id)
        await update.message.reply_text(message, parse_mode="Markdown")

    async def web_search_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_web_search_on"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.web_search_on(admin_id)
        await update.message.reply_text(message)

    async def web_search_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_web_search_off"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.web_search_off(admin_id)
        await update.message.reply_text(message)

    async def web_search_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_web_search_status"""
        admin_id = update.effective_user.id if update.effective_user else 0
        _success, message = self._commands.web_search_status(admin_id)
        await update.message.reply_text(message, parse_mode="Markdown")

    async def backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/backup — create and send a backup archive (admin only)."""
        admin_id = update.effective_user.id if update.effective_user else 0
        success, message, zip_path = self._commands.create_backup(admin_id)
        if not success or zip_path is None:
            await update.message.reply_text(message)
            return
        try:
            with open(zip_path, "rb") as f:
                await update.message.reply_document(document=f, filename="backup.zip")
        except Exception as exc:
            logger.error("Failed to send backup document: %s", exc)
            await update.message.reply_text(f"❌ Ошибка при отправке архива: {exc}")
        finally:
            zip_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_int_arg(context: ContextTypes.DEFAULT_TYPE) -> int | None:
        if context.args and len(context.args) == 1:
            try:
                return int(context.args[0])
            except ValueError:
                return None
        return None

