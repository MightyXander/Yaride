"""Пользовательские фильтры для aiogram."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


class RatingReviewReplyFilter(BaseFilter):
    """Срабатывает на ответ реплаем на сообщение с запросом текстового отзыва к оценке."""

    async def __call__(self, message: Message, state: FSMContext) -> bool | dict[str, tuple[int, int, int]]:
        if not message.reply_to_message or message.text is None:
            return False
        data = await state.get_data()
        pending = data.get("rating_review_collect")
        if not pending or not isinstance(pending, tuple) or len(pending) != 4:
            return False
        trip_id, rated_tg, stars, prompt_mid = pending
        if message.reply_to_message.message_id != prompt_mid:
            return False
        return {"rating_completion": (trip_id, rated_tg, stars)}
