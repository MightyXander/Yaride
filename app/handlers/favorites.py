"""Избранные маршруты: меню, fav_add, выбор даты по избранному."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.repo import Repo
from app.states import TripSearch

router = Router()


@router.message(F.text == "Избранные маршруты")
async def favorite_routes_menu(message: Message, repo: Repo) -> None:
    from app.bot_support import (
        close_flow,
        delete_user_message,
        favorite_routes_keyboard,
        main_keyboard,
        open_flow,
        send_post_flow_message,
        with_back_button,
    )

    user = repo.users.get_user(message.from_user.id)
    await delete_user_message(message)
    if not user:
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
        return
    rows = repo.favorites.list_favorites(message.from_user.id)
    if not rows:
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Пока нет избранных маршрутов. После успешной брони можно добавить маршрут кнопкой под сообщением.",
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
        return
    await open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind="favorites",
        text="Избранные маршруты — нажми маршрут, затем выбери дату поездки:",
        inline_markup=with_back_button(favorite_routes_keyboard(rows), target="menu"),
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
async def favorite_route_pick_date(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import add_back_button, update_flow
    from app.yaride_calendar import trip_calendar

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
        await update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind="favorites",
            text=f"{row['start_title']} → {row['end_title']}\nВыбери дату поездки:",
            inline_markup=add_back_button(await trip_calendar().start_calendar(), "menu"),
        )
    await callback.answer()
