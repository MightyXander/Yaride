"""Фоновая отправка напоминаний об оценках после поездки.

Логику можно вынести в отдельный процесс (только БД + Bot API), не трогая основной polling.
"""

from __future__ import annotations

import logging

from aiogram import Bot

from app.repo import Repo
from app.ui import KeyboardFactory

logger = logging.getLogger(__name__)
# Экземпляр без настроек — только rating_stars_keyboard, которому настройки не нужны.
_kb = KeyboardFactory()


async def process_pending_rating_prompts(bot: Bot, repo: Repo) -> None:
    """Отправить запросы оценок всем участникам завершившихся поездок, которые ещё не получили напоминание.

    mark_rating_prompt_sent вызывается только после успешной отправки — если Telegram вернул ошибку,
    пользователь получит напоминание в следующем цикле.
    """
    prompts = repo.ratings.list_pending_rating_prompts()
    for p in prompts:
        markup = _kb.rating_stars_keyboard(p.trip_id, p.rated_tg_user_id)
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
