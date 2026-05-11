"""Обработка SimpleCalendarCallback: поиск, создание поездки, смена роли."""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram_calendar import SimpleCalendarCallback

from app.formatting import format_trip_row
from app.repo import Repo
from app.states import TripCreate
from app.yaride_calendar import trip_calendar

router = Router()


@router.callback_query(SimpleCalendarCallback.filter())
async def process_calendar_selection(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
    repo: Repo,
) -> None:
    from app.bot_support import (
        STALE_CREATE_FLOW,
        STALE_SEARCH_FLOW,
        add_back_button,
        edit_or_send_clean,
        main_keyboard,
        time_keyboard,
        trips_keyboard,
    )

    selected, selected_date = await trip_calendar().process_selection(callback, callback_data)
    if not selected:
        return

    if isinstance(selected_date, datetime):
        iso_date = selected_date.date().isoformat()
    elif isinstance(selected_date, date_cls):
        iso_date = selected_date.isoformat()
    else:
        iso_date = str(selected_date)[:10]
    data = await state.get_data()
    target = data.get("calendar_target")

    if target == "search":
        if "start_point" not in data or "end_point" not in data:
            await state.clear()
            await edit_or_send_clean(
                callback, STALE_SEARCH_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id)
            )
            await callback.answer()
            return
        await state.update_data(trip_date=iso_date)
        trips = repo.trips.find_open_trips(
            start_point_id=data.get("start_point"),
            end_point_id=data.get("end_point"),
            trip_date=iso_date,
        )
        await state.clear()
        if not trips:
            await edit_or_send_clean(
                callback, "Подходящих поездок пока нет.", reply_markup=main_keyboard(repo, callback.from_user.id)
            )
            await callback.answer()
            return
        text_lines = ["Доступные поездки:"]
        for t in trips:
            free = t["seats_total"] - t["seats_booked"]
            text_lines.append(
                f"#{t['id']} | {t['driver_name']} ({float(t['driver_rating']):.1f}) | "
                f"{t['start_title']} -> {t['end_title']} | {format_trip_row(t)} | "
                f"{t['price_rub']} руб. | свободно {free}/{t['seats_total']}"
            )
        await edit_or_send_clean(callback, "\n".join(text_lines), reply_markup=trips_keyboard(trips))
        await callback.answer()
        return

    if target == "create":
        if "start_point" not in data or "end_point" not in data:
            await state.clear()
            await edit_or_send_clean(
                callback, STALE_CREATE_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id)
            )
            await callback.answer()
            return
        await state.update_data(trip_date=iso_date)
        await state.set_state(TripCreate.departure_time)
        await edit_or_send_clean(
            callback,
            "Выбери время отправления:",
            reply_markup=add_back_button(time_keyboard("create_time"), "create_date"),
        )
        await callback.answer()
        return

    if target == "switch_role":
        target_role = data.get("target_role")
        if not target_role:
            await state.clear()
            await edit_or_send_clean(callback, "Сессия смены роли устарела. Нажми «Сменить роль» снова.")
            await callback.answer()
            return
        _, msg = repo.users.switch_role(callback.from_user.id, str(target_role), iso_date)
        await state.clear()
        await edit_or_send_clean(callback, msg, reply_markup=main_keyboard(repo, callback.from_user.id))
        await callback.answer()
        return

    await callback.answer("Сессия выбора даты не найдена. Начни заново.", show_alert=True)
