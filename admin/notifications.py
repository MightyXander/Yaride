"""Отправка уведомлений пользователям из админки через Bot API.

Используется отдельный экземпляр Bot с тем же BOT_TOKEN, что и у бота-поллера: отправка сообщений
не конфликтует с long-polling (конфликтует только getUpdates). Ошибки доставки не должны ломать
основное действие администратора — они логируются и проглатываются.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from app.services.admin_service import AdminNotification

logger = logging.getLogger(__name__)


class Notifier:
    """Обёртка над aiogram.Bot. Создаётся один раз на жизненный цикл приложения; None — уведомления выключены."""

    def __init__(self, bot_token: str | None) -> None:
        self._token = bot_token
        self._bot = None

    @property
    def enabled(self) -> bool:
        return self._token is not None

    def _ensure_bot(self):
        if self._bot is None and self._token:
            from aiogram import Bot

            self._bot = Bot(token=self._token)
        return self._bot

    async def send(self, notifications: Iterable[AdminNotification]) -> None:
        bot = self._ensure_bot()
        if bot is None:
            return
        for note in notifications:
            try:
                await bot.send_message(note.tg_user_id, note.text)
            except Exception as err:
                logger.warning("Admin notify failed tg=%s: %s", note.tg_user_id, err)

    async def close(self) -> None:
        if self._bot is not None:
            await self._bot.session.close()
            self._bot = None
