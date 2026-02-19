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
