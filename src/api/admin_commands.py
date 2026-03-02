"""Admin command processor for managing bot settings at runtime.

This module provides a unified interface for admin commands that can be used
by both Telegram bot handlers and CLI interface.
"""

from __future__ import annotations

from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings


class AdminCommandService:
    """Service for processing admin commands independently of the interface.

    This service handles all admin command logic and returns results as
    (success: bool, message: str) tuples for use in any interface (Telegram, CLI, etc).
    """

    def __init__(self, settings: AppSettings, access_filter: AccessFilter) -> None:
        """Initialize admin command service.

        Args:
            settings: Application settings
            access_filter: Access control filter
        """
        self._settings = settings
        self._access = access_filter

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is an admin, False otherwise
        """
        return self._access.is_admin(user_id)

    def add_user(self, user_id: int, admin_id: int) -> tuple[bool, str]:
        """Add a user to the allowed list.

        Args:
            user_id: User ID to add
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        if user_id in self._settings.access.allowed_user_ids:
            return False, f"Пользователь {user_id} уже в списке."

        self._settings.access.allowed_user_ids.append(user_id)
        self._settings.save_access()
        return True, f"✅ Пользователь {user_id} добавлен."

    def remove_user(self, user_id: int, admin_id: int) -> tuple[bool, str]:
        """Remove a user from the allowed list.

        Args:
            user_id: User ID to remove
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        if user_id not in self._settings.access.allowed_user_ids:
            return False, f"Пользователь {user_id} не найден в списке."

        self._settings.access.allowed_user_ids.remove(user_id)
        self._settings.save_access()
        return True, f"✅ Пользователь {user_id} удалён."

    def add_chat(self, chat_id: int, admin_id: int) -> tuple[bool, str]:
        """Add a chat to the allowed list.

        Args:
            chat_id: Chat ID to add
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        if chat_id in self._settings.access.allowed_chat_ids:
            return False, f"Чат {chat_id} уже в списке."

        self._settings.access.allowed_chat_ids.append(chat_id)
        self._settings.save_access()
        return True, f"✅ Чат {chat_id} добавлен."

    def remove_chat(self, chat_id: int, admin_id: int) -> tuple[bool, str]:
        """Remove a chat from the allowed list.

        Args:
            chat_id: Chat ID to remove
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        if chat_id not in self._settings.access.allowed_chat_ids:
            return False, f"Чат {chat_id} не найден в списке."

        self._settings.access.allowed_chat_ids.remove(chat_id)
        self._settings.save_access()
        return True, f"✅ Чат {chat_id} удалён."

    def list_access(self, admin_id: int) -> tuple[bool, str]:
        """Get current access lists.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

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

        # Show effective reasoning mode status (both config and runtime must be enabled)
        reasoning_config_enabled = self._settings.mistral.reasoning_mode
        reasoning_runtime_enabled = self._settings.access.reasoning_mode_enabled
        reasoning_effective = reasoning_config_enabled and reasoning_runtime_enabled
        reasoning_status = "Включён ✅" if reasoning_effective else "Выключен ❌"

        message = (
            "📋 *Текущие настройки доступа:*\n\n"
            f"*Пользователи:*\n{_format_list(users)}\n\n"
            f"*Чаты:*\n{_format_list(chats)}\n\n"
            f"*Реакции:* {reactions_status}\n"
            f"*Добавление даты:* {date_status}\n"
            f"*Режим рассуждения (CoT):* {reasoning_status}"
        )
        return True, message

    def reactions_on(self, admin_id: int) -> tuple[bool, str]:
        """Enable automatic message reactions.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.reactions.enabled = True
        self._settings.access.reactions_enabled = True
        self._settings.save_access()
        return True, "✅ Реакции на сообщения включены."

    def reactions_off(self, admin_id: int) -> tuple[bool, str]:
        """Disable automatic message reactions.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.reactions.enabled = False
        self._settings.access.reactions_enabled = False
        self._settings.save_access()
        return True, "✅ Реакции на сообщения выключены."

    def reactions_status(self, admin_id: int) -> tuple[bool, str]:
        """Get current reactions status and settings.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        # Check both config and runtime flags
        config_enabled = self._settings.reactions.enabled
        runtime_enabled = self._settings.access.reactions_enabled
        effective = config_enabled and runtime_enabled

        status = "включены ✅" if effective else "выключены ❌"
        message = (
            f"*Статус реакций:* {status}\n\n"
            f"*Настройки:*\n"
            f"• Конфигурация: {'включена' if config_enabled else 'выключена'}\n"
            f"• Рантайм-переключатель: {'включён' if runtime_enabled else 'выключен'}\n"
            f"• Модель: `{self._settings.reactions.model}`\n"
            f"• Вероятность: {self._settings.reactions.probability * 100:.0f}%\n"
            f"• Мин. слов: {self._settings.reactions.min_words}\n"
            f"• Настроения: {len(self._settings.reactions.moods)}"
        )
        return True, message

    def date_on(self, admin_id: int) -> tuple[bool, str]:
        """Enable always appending date to system prompt.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.mistral.always_append_date = True
        self._settings.access.always_append_date_enabled = True
        self._settings.save_access()
        return True, "✅ Автоматическое добавление даты в системный промпт включено."

    def date_off(self, admin_id: int) -> tuple[bool, str]:
        """Disable always appending date to system prompt.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.mistral.always_append_date = False
        self._settings.access.always_append_date_enabled = False
        self._settings.save_access()
        return True, "✅ Автоматическое добавление даты в системный промпт выключено."

    def date_status(self, admin_id: int) -> tuple[bool, str]:
        """Get current date appending status and settings.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        # Check both config and runtime flags
        config_enabled = self._settings.mistral.always_append_date
        runtime_enabled = self._settings.access.always_append_date_enabled
        effective = config_enabled and runtime_enabled

        status = "включено ✅" if effective else "выключено ❌"
        message = (
            f"*Статус добавления даты:* {status}\n\n"
            f"*Настройки:*\n"
            f"• Конфигурация: {'включена' if config_enabled else 'выключена'}\n"
            f"• Рантайм-переключатель: {'включён' if runtime_enabled else 'выключен'}\n\n"
            f"*Как работает:*\n"
            f"Если включено, текущая дата всегда добавляется к системному промпту, "
            f"даже если ключевые слова не обнаружены в запросе.\n\n"
            f"Это гарантирует, что бот всегда знает текущую дату."
        )
        return True, message


    def reasoning_on(self, admin_id: int) -> tuple[bool, str]:
        """Enable chain-of-thought reasoning mode.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.mistral.reasoning_mode = True
        self._settings.access.reasoning_mode_enabled = True
        self._settings.save_access()
        return True, "✅ Режим рассуждения (chain-of-thought) включён."

    def reasoning_off(self, admin_id: int) -> tuple[bool, str]:
        """Disable chain-of-thought reasoning mode.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.mistral.reasoning_mode = False
        self._settings.access.reasoning_mode_enabled = False
        self._settings.save_access()
        return True, "✅ Режим рассуждения (chain-of-thought) выключен."

    def reasoning_status(self, admin_id: int) -> tuple[bool, str]:
        """Get current reasoning mode status and settings.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        config_enabled = self._settings.mistral.reasoning_mode
        runtime_enabled = self._settings.access.reasoning_mode_enabled
        effective = config_enabled and runtime_enabled

        status = "включён ✅" if effective else "выключен ❌"
        message = (
            f"*Статус режима рассуждения (CoT):* {status}\n\n"
            f"*Настройки:*\n"
            f"• Конфигурация: {'включена' if config_enabled else 'выключена'}\n"
            f"• Рантайм-переключатель: {'включён' if runtime_enabled else 'выключен'}\n\n"
            f"*Как работает:*\n"
            f"Если включено, к системному промпту добавляется инструкция "
            f"думать шаг за шагом и подробно объяснять рассуждения (chain-of-thought)."
        )
        return True, message

    def web_search_on(self, admin_id: int) -> tuple[bool, str]:
        """Enable web search.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.mistral.enable_web_search = True
        self._settings.save_access()
        return True, "✅ Веб-поиск включён."

    def web_search_off(self, admin_id: int) -> tuple[bool, str]:
        """Disable web search.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        self._settings.mistral.enable_web_search = False
        self._settings.save_access()
        return True, "✅ Веб-поиск выключен."

    def web_search_status(self, admin_id: int) -> tuple[bool, str]:
        """Get current web search status.

        Args:
            admin_id: ID of the admin executing the command

        Returns:
            Tuple of (success, message)
        """
        if not self.is_admin(admin_id):
            return False, "⛔ У вас нет прав администратора."

        enabled = self._settings.mistral.enable_web_search
        status = "включён ✅" if enabled else "выключен ❌"
        message = (
            f"*Статус веб-поиска:* {status}\n\n"
            f"*Как работает:*\n"
            f"Если включено, бот выполняет поиск в интернете для актуальных запросов "
            f"(новости, погода, текущие события и т.д.)."
        )
        return True, message


def _format_list(items: list) -> str:
    """Format a list of items for display.

    Args:
        items: List of items to format

    Returns:
        Formatted string with bullet points
    """
    return "\n".join(f"• `{item}`" for item in items)
