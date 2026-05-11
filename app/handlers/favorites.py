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
    from app.bot_support import favorite_routes_keyboard, send_clean_message

    user = repo.users.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    rows = repo.favorites.list_favorites(message.from_user.id)
    if not rows:
        await send_clean_message(
            message,
            "Пока нет избранных маршрутов. После успешной брони можно добавить маршрут кнопкой под сообщением.",
        )
        return
    await send_clean_message(
        message,
        "Избранные маршруты — нажми маршрут, затем выбери дату поездки:",
        reply_markup=favorite_routes_keyboard(rows),
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
    from app.bot_support import add_back_button, edit_or_send_clean
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
    await edit_or_send_clean(
        callback,
        f"{row['start_title']} → {row['end_title']}\nВыбери дату поездки:",
        reply_markup=add_back_button(await trip_calendar().start_calendar(), "menu"),
    )
    await callback.answer()
