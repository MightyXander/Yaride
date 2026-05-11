"""Оценки поездок: callback rate:, ответ на ForceReply с комментарием."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ForceReply, Message

from app.filters import RatingReviewReplyFilter
from app.repo import Repo
from app.security.rating_input import MAX_REVIEW_CHARS, parse_rate_callback_data
from app.services.rating_service import RatingService

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("rate:"))
async def submit_trip_rating_callback(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    parsed = parse_rate_callback_data(callback.data or "")
    if not parsed:
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    trip_id, rated_tg, stars = parsed
    if callback.message is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    prompt = await callback.message.answer(
        f"Оценка {stars}★.\nОтветь на это сообщение: короткий комментарий (до {MAX_REVIEW_CHARS} символов) "
        "или отправь «-» без текста.",
        reply_markup=ForceReply(input_field_placeholder="Комментарий или -"),
    )
    await state.update_data(rating_review_collect=(trip_id, rated_tg, stars, prompt.message_id))
    await callback.answer()


@router.message(RatingReviewReplyFilter())
async def complete_trip_rating_review(
    message: Message,
    state: FSMContext,
    repo: Repo,
    rating_completion: tuple[int, int, int],
) -> None:
    trip_id, rated_tg, stars = rating_completion
    svc = RatingService(repo)
    try:
        svc.submit(message.from_user.id, trip_id, rated_tg, stars, message.text)
    except ValueError as exc:
        logger.info(
            "critical action=%s tg_user_id=%s trip_id=%s outcome=%s reason=%s",
            "submit_rating",
            message.from_user.id,
            trip_id,
            "rejected",
            str(exc),
        )
        await state.update_data(rating_review_collect=None)
        await message.answer(str(exc))
        return
    logger.info(
        "critical action=%s tg_user_id=%s trip_id=%s stars=%s outcome=%s",
        "submit_rating",
        message.from_user.id,
        trip_id,
        stars,
        "success",
    )
    await state.update_data(rating_review_collect=None)
    await message.answer("Спасибо, оценка сохранена.")
