"""Назад (callback и reply) и универсальный fallback-сообщение — регистрировать последним."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.chat_ui import ChatUiService
from app.navigation_flow import NavigationFlow
from app.repo import Repo
from app.ui import KeyboardFactory

router = Router()


@router.callback_query(F.data.startswith("back:"))
async def go_back(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    nav: NavigationFlow,
) -> None:
    await nav.handle_callback_back(callback, state, repo)


@router.message(F.text == "⬅ Назад")
async def go_back_keyboard(
    message: Message,
    state: FSMContext,
    repo: Repo,
    nav: NavigationFlow,
    chat_ui: ChatUiService,
) -> None:
    await chat_ui.delete_user_message(message)
    await nav.handle_reply_back(message, state, repo)


@router.message()
async def fallback(
    message: Message,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    await chat_ui.delete_user_message(message)
    await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
    u = repo.users.get_user(message.from_user.id)
    await chat_ui.replace_with_notice(
        chat_id=message.chat.id,
        bot=message.bot,
        text="Используй кнопки меню или /start для регистрации.",
        reply_keyboard=keyboards.main_keyboard(is_driver=u is not None and u["role"] == "driver"),
    )
