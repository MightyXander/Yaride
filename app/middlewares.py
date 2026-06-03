"""Middleware бота. BanMiddleware отсекает забаненных пользователей до доменных хендлеров.

Регистрируется как outer-middleware на observer'е update: проверка идёт один раз для любого апдейта
(сообщение, callback, и т.п.). Забаненному не отвечаем — он уже уведомлён в момент бана из админки.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.repo import Repo


class BanMiddleware(BaseMiddleware):
    def __init__(self, repo: Repo) -> None:
        self._repo = repo

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user_id = self._extract_user_id(event, data)
        if tg_user_id is not None and self._repo.users.is_banned(tg_user_id):
            return None
        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event: TelegramObject, data: dict[str, Any]) -> int | None:
        user = data.get("event_from_user")
        if user is not None:
            return int(user.id)
        if isinstance(event, Update):
            source = event.message or event.callback_query or event.inline_query
            if source is not None and source.from_user is not None:
                return int(source.from_user.id)
        return None
