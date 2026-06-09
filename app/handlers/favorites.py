"""Избранные маршруты: меню, fav_add, выбор даты по избранному."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.chat_ui import ChatUiService
from app.repo import Repo
from app.states import TripSearch
from app.ui import KeyboardFactory
from app.yaride_calendar import trip_calendar

router = Router()


def _mk(repo: Repo, keyboards: KeyboardFactory, tg_user_id: int):
    u = repo.users.get_user(tg_user_id)
    return keyboards.main_keyboard(is_driver=repo.users.is_active_driver(tg_user_id))


@router.message(F.text == "Избранные маршруты")
async def favorite_routes_menu(
    message: Message,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    user = repo.users.get_user(message.from_user.id)
    await chat_ui.delete_user_message(message)
    if not user:
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=_mk(repo, keyboards, message.from_user.id),
        )
        return
    rows = repo.favorites.list_favorites(message.from_user.id)
    if not rows:
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Пока нет избранных маршрутов. После успешной брони можно добавить маршрут кнопкой под сообщением.",
            reply_keyboard=_mk(repo, keyboards, message.from_user.id),
        )
        return
    await chat_ui.open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind="favorites",
        text="Избранные маршруты — нажми маршрут, затем выбери дату поездки:",
        inline_markup=keyboards.with_back_button(keyboards.favorite_routes_keyboard(rows), target="menu"),
    )


@router.callback_query(F.data.startswith("fav_add:"))
async def fav_add(callback: CallbackQuery, repo: Repo) -> None:
    if not repo.users.get_user(callback.from_user.id):
        await callback.answer("Сначала /start.", show_alert=True)
        return
    tid = int(callback.data.split(":")[1])
    try:
        added = repo.favorites.add_favorite_from_trip(callback.from_user.id, tid)
    except ValueError:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    await callback.answer("Маршрут добавлен в избранное" if added else "Этот маршрут уже в избранном")


@router.callback_query(F.data.startswith("fav_route:"))
async def favorite_route_pick_date(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
) -> None:
    fid = int(callback.data.split(":")[1])
    row = repo.favorites.get_favorite_owned(callback.from_user.id, fid)
    if not row:
        await callback.answer("Маршрут не найден.", show_alert=True)
        return
    await state.set_state(TripSearch.trip_date)
    await state.update_data(
        start_point=int(row["start_point_id"]),
        end_point=int(row["end_point_id"]),
        calendar_target="search",
    )
    if callback.message:
        await chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind="favorites",
            text=f"{row['start_title']} → {row['end_title']}\nВыбери дату поездки:",
            inline_markup=await trip_calendar().start_calendar(),
        )
    await callback.answer()
