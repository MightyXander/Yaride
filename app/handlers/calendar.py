"""Обработка SimpleCalendarCallback: поиск, создание поездки, смена роли."""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram_calendar import SimpleCalendarCallback

from app.bot_support import STALE_CREATE_FLOW, STALE_SEARCH_FLOW
from app.chat_ui import ChatUiService
from app.formatting import format_trip_row
from app.repo import Repo
from app.states import TripCreate
from app.ui import KeyboardFactory
from app.yaride_calendar import trip_calendar

router = Router()


@router.callback_query(SimpleCalendarCallback.filter())
async def process_calendar_selection(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
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

    def _mk(tg_user_id: int):
        u = repo.users.get_user(tg_user_id)
        return keyboards.main_keyboard(is_driver=u is not None and u["role"] == "driver")

    if target == "search":
        if "start_point" not in data or "end_point" not in data:
            await state.clear()
            if callback.message:
                await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
                await chat_ui.replace_with_notice(
                    chat_id=callback.message.chat.id,
                    bot=callback.bot,
                    text=STALE_SEARCH_FLOW,
                    reply_keyboard=_mk(callback.from_user.id),
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
            if callback.message:
                await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
                await chat_ui.replace_with_notice(
                    chat_id=callback.message.chat.id,
                    bot=callback.bot,
                    text="Подходящих поездок пока нет.",
                    reply_keyboard=_mk(callback.from_user.id),
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
        if callback.message:
            await chat_ui.update_flow(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                flow_kind="search",
                text="\n".join(text_lines),
                inline_markup=keyboards.trips_keyboard(trips),
                reply_keyboard=None,
            )
        await callback.answer()
        return

    if target == "create":
        if "start_point" not in data or "end_point" not in data:
            await state.clear()
            if callback.message:
                await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
                await chat_ui.replace_with_notice(
                    chat_id=callback.message.chat.id,
                    bot=callback.bot,
                    text=STALE_CREATE_FLOW,
                    reply_keyboard=_mk(callback.from_user.id),
                )
            await callback.answer()
            return
        await state.update_data(trip_date=iso_date)
        await state.set_state(TripCreate.departure_time)
        if callback.message:
            await chat_ui.update_flow(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                flow_kind="create",
                text="Выбери время отправления:",
                inline_markup=keyboards.time_keyboard("create_time"),
            )
        await callback.answer()
        return

    if target == "switch_role":
        target_role = data.get("target_role")
        if not target_role:
            await state.clear()
            if callback.message:
                await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
                await chat_ui.replace_with_notice(
                    chat_id=callback.message.chat.id,
                    bot=callback.bot,
                    text="Сессия смены роли устарела. Нажми «Сменить роль» снова.",
                    reply_keyboard=_mk(callback.from_user.id),
                )
            await callback.answer()
            return
        _, msg = repo.users.switch_role(callback.from_user.id, str(target_role), iso_date)
        await state.clear()
        if callback.message:
            await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
            await chat_ui.replace_with_notice(
                chat_id=callback.message.chat.id,
                bot=callback.bot,
                text=msg,
                reply_keyboard=_mk(callback.from_user.id),
            )
        await callback.answer()
        return

    await callback.answer("Сессия выбора даты не найдена. Начни заново.", show_alert=True)
