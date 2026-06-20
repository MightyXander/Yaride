"""Фоновая отправка напоминаний об оценках после поездки.

Логику можно вынести в отдельный процесс (только БД + Bot API), не трогая основной polling.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types.web_app_info import WebAppInfo

from app.config import Settings
from app.repo import Repo

logger = logging.getLogger(__name__)


def _make_rating_deep_link_keyboard(miniapp_url: str, trip_id: int) -> InlineKeyboardMarkup:
    """Создать клавиатуру с deep-link на Mini App для оценки поездки."""
    deep_link = f"{miniapp_url}#/rate/{trip_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Оценить поездку", web_app=WebAppInfo(url=deep_link))]]
    )


async def process_pending_rating_prompts(bot: Bot, repo: Repo, settings: Settings) -> None:
    """Отправить запросы оценок всем участникам завершившихся поездок, которые ещё не получили напоминание.

    mark_rating_prompt_sent вызывается только после успешной отправки — если Telegram вернул ошибку,
    пользователь получит напоминание в следующем цикле.
    """
    prompts = repo.ratings.list_pending_rating_prompts()
    for p in prompts:
        if settings.miniapp_url:
            markup = _make_rating_deep_link_keyboard(settings.miniapp_url, p.trip_id)
        else:
            markup = None
        try:
            await bot.send_message(p.rater_tg_user_id, p.prompt_text, reply_markup=markup)
            repo.ratings.mark_rating_prompt_sent(p.trip_id, p.rater_user_id, p.rated_user_id)
        except Exception as err:
            logger.warning(
                "Не удалось отправить напоминание об оценке trip=%s rater=%s: %s",
                p.trip_id,
                p.rater_tg_user_id,
                err,
            )
