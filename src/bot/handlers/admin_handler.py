"""Admin-only Telegram commands for managing bot settings at runtime."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

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
        self._settings = settings
        self._access = access_filter

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _is_admin(self, update: Update) -> bool:
        user_id = update.effective_user.id if update.effective_user else 0
        return self._access.is_admin(user_id)

    async def _reject(self, update: Update) -> None:
        if update.message:
            await update.message.reply_text("⛔ У вас нет прав администратора.")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def add_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_add_user <user_id>"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        uid = self._parse_int_arg(context)
        if uid is None:
            await update.message.reply_text("Использование: /admin_add_user <user_id>")
            return
        if uid not in self._settings.access.allowed_user_ids:
            self._settings.access.allowed_user_ids.append(uid)
            self._settings.save_access()
            await update.message.reply_text(f"✅ Пользователь {uid} добавлен.")
        else:
            await update.message.reply_text(f"Пользователь {uid} уже в списке.")

    async def remove_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_remove_user <user_id>"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        uid = self._parse_int_arg(context)
        if uid is None:
            await update.message.reply_text("Использование: /admin_remove_user <user_id>")
            return
        if uid in self._settings.access.allowed_user_ids:
            self._settings.access.allowed_user_ids.remove(uid)
            self._settings.save_access()
            await update.message.reply_text(f"✅ Пользователь {uid} удалён.")
        else:
            await update.message.reply_text(f"Пользователь {uid} не найден в списке.")

    async def add_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_add_chat <chat_id>"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        cid = self._parse_int_arg(context)
        if cid is None:
            await update.message.reply_text("Использование: /admin_add_chat <chat_id>")
            return
        if cid not in self._settings.access.allowed_chat_ids:
            self._settings.access.allowed_chat_ids.append(cid)
            self._settings.save_access()
            await update.message.reply_text(f"✅ Чат {cid} добавлен.")
        else:
            await update.message.reply_text(f"Чат {cid} уже в списке.")

    async def remove_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_remove_chat <chat_id>"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        cid = self._parse_int_arg(context)
        if cid is None:
            await update.message.reply_text("Использование: /admin_remove_chat <chat_id>")
            return
        if cid in self._settings.access.allowed_chat_ids:
            self._settings.access.allowed_chat_ids.remove(cid)
            self._settings.save_access()
            await update.message.reply_text(f"✅ Чат {cid} удалён.")
        else:
            await update.message.reply_text(f"Чат {cid} не найден в списке.")

    async def list_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_list"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        users = self._settings.access.allowed_user_ids or ["(пусто)"]
        chats = self._settings.access.allowed_chat_ids or ["(пусто)"]
        reactions_status = "Включены ✅" if self._settings.access.reactions_enabled else "Выключены ❌"
        text = (
            "📋 *Текущие настройки доступа:*\n\n"
            f"*Пользователи:*\n{_format_list(users)}\n\n"
            f"*Чаты:*\n{_format_list(chats)}\n\n"
            f"*Реакции:* {reactions_status}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def reactions_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reactions_on"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        self._settings.access.reactions_enabled = True
        self._settings.save_access()
        await update.message.reply_text("✅ Реакции на сообщения включены.")

    async def reactions_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reactions_off"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        self._settings.access.reactions_enabled = False
        self._settings.save_access()
        await update.message.reply_text("✅ Реакции на сообщения выключены.")

    async def reactions_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/admin_reactions_status"""
        if not self._is_admin(update):
            await self._reject(update)
            return
        status = "включены ✅" if self._settings.access.reactions_enabled else "выключены ❌"
        text = (
            f"*Статус реакций:* {status}\n\n"
            f"*Настройки:*\n"
            f"• Модель: `{self._settings.reactions.model}`\n"
            f"• Вероятность: {self._settings.reactions.probability * 100:.0f}%\n"
            f"• Мин. слов: {self._settings.reactions.min_words}\n"
            f"• Настроения: {len(self._settings.reactions.moods)}"
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


def _format_list(items: list) -> str:
    return "\n".join(f"• `{item}`" for item in items)
