"""Назад (callback и reply) и универсальный fallback-сообщение — регистрировать последним."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.repo import Repo

router = Router()


@router.callback_query(F.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import NAVIGATION_FLOW

    assert NAVIGATION_FLOW is not None
    await NAVIGATION_FLOW.handle_callback_back(callback, state, repo)


@router.message(F.text == "⬅ Назад")
async def go_back_keyboard(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import NAVIGATION_FLOW

    assert NAVIGATION_FLOW is not None
    await NAVIGATION_FLOW.handle_reply_back(message, state, repo)


@router.message()
async def fallback(message: Message, repo: Repo) -> None:
    from app.bot_support import main_keyboard, send_clean_message

    await send_clean_message(
        message,
        "Используй кнопки меню или /start для регистрации.",
        reply_markup=main_keyboard(repo, message.from_user.id),
    )
