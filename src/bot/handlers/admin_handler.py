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
        if not self._is_admin(update):
            await self._reject(update)
            return
        users = self._settings.access.allowed_user_ids or ["(пусто)"]
        chats = self._settings.access.allowed_chat_ids or ["(пусто)"]

        # Show effective reactions status (both config and runtime must be enabled)
        config_enabled = self._settings.reactions.enabled
        runtime_enabled = self._settings.access.reactions_enabled
        effective = config_enabled and runtime_enabled
        reactions_status = "Включены ✅" if effective else "Выключены ❌"

        # Show effective date status (both config and runtime must be enabled)
        date_config_enabled = self._settings.mistral.always_append_date
        date_runtime_enabled = self._settings.access.always_append_date_enabled
        date_effective = date_config_enabled and date_runtime_enabled
        date_status = "Включено ✅" if date_effective else "Выключено ❌"

        text = (
            "📋 *Текущие настройки доступа:*\n\n"
            f"*Пользователи:*\n{_format_list(users)}\n\n"
            f"*Чаты:*\n{_format_list(chats)}\n\n"
            f"*Реакции:* {reactions_status}\n"
            f"*Добавление даты:* {date_status}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

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
        if not self._is_admin(update):
            await self._reject(update)
            return
        self._settings.access.always_append_date_enabled = True
        self._settings.save_access()
        await update.message.reply_text(
            "✅ Автоматическое добавление даты в системный промпт включено."
        )

    async def date_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_date_off"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        self._settings.access.always_append_date_enabled = False
        self._settings.save_access()
        await update.message.reply_text(
            "✅ Автоматическое добавление даты в системный промпт выключено."
        )

    async def date_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_date_status"""
        if not self._is_admin(update):
            await self._reject(update)
            return

        # Check both config and runtime flags
        config_enabled = self._settings.mistral.always_append_date
        runtime_enabled = self._settings.access.always_append_date_enabled
        effective = config_enabled and runtime_enabled

        status = "включено ✅" if effective else "выключено ❌"
        text = (
            f"*Статус добавления даты:* {status}\n\n"
            f"*Настройки:*\n"
            f"• Конфигурация: {'включена' if config_enabled else 'выключена'}\n"
            f"• Рантайм-переключатель: {'включён' if runtime_enabled else 'выключен'}\n\n"
            f"*Как работает:*\n"
            f"Если включено, текущая дата всегда добавляется к системному промпту, "
            f"даже если ключевые слова не обнаружены в запросе.\n\n"
            f"Это гарантирует, что бот всегда знает текущую дату."
        )
        await update.message.reply_text(text, parse_mode="Markdown")

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
