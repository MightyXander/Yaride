"""Бронирование: book:, список броней, отмена пассажиром."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.formatting import format_trip_row, format_trip_when
from app.repo import Repo
from app.states import CancelBooking

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("book:"))
async def book_trip(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot_support import (
        add_favorite_keyboard,
        edit_or_send_clean,
        main_keyboard,
        track_bot_message,
    )

    trip_id = int(callback.data.split(":")[1])
    user = repo.users.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start.", show_alert=True)
        return
    if user["role"] != "passenger":
        await callback.answer("Бронировать поездки может только пассажир.", show_alert=True)
        return
    try:
        booking_id = repo.bookings.create_booking(callback.from_user.id, trip_id)
    except ValueError as exc:
        logger.info(
            "critical action=%s tg_user_id=%s trip_id=%s outcome=%s reason=%s",
            "book_trip",
            callback.from_user.id,
            trip_id,
            "rejected",
            str(exc),
        )
        await callback.answer(str(exc), show_alert=True)
        return
    logger.info(
        "critical action=%s tg_user_id=%s trip_id=%s booking_id=%s outcome=%s",
        "book_trip",
        callback.from_user.id,
        trip_id,
        booking_id,
        "success",
    )

    trip_item = repo.trips.get_trip_public_card(trip_id)
    await edit_or_send_clean(
        callback,
        f"Бронь #{booking_id} создана.\n\nДобавить этот маршрут в избранное?",
        reply_markup=add_favorite_keyboard(trip_id),
    )
    sent = await callback.message.answer(
        "Готово — ниже клавиатура меню.",
        reply_markup=main_keyboard(repo, callback.from_user.id),
    )
    await track_bot_message(sent)
    if trip_item:
        driver_internal_id = trip_item["driver_id"]
        with repo.db.transaction() as conn:
            drow = conn.execute(
                "SELECT tg_user_id FROM users WHERE id = ?",
                (driver_internal_id,),
            ).fetchone()
        if drow:
            try:
                await callback.bot.send_message(
                    int(drow["tg_user_id"]),
                    (
                        "Новая бронь на вашу поездку.\n"
                        f"Trip #{trip_id} | {trip_item['start_title']} -> {trip_item['end_title']} | "
                        f"{format_trip_when(trip_item['trip_date'], trip_item['departure_time'], trip_item['time_slot'])}"
                    ),
                    reply_markup=add_favorite_keyboard(trip_id),
                )
            except Exception as err:
                logger.warning("Driver notify failed: %s", err)
    await callback.answer("Забронировано")


@router.message(F.text == "Мои брони")
async def my_bookings(message: Message, repo: Repo) -> None:
    from app.bot_support import (
        cancel_booking_keyboard,
        flow_keyboard,
        send_clean_message,
        send_flow_step,
    )

    user = repo.users.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    bookings = repo.bookings.list_passenger_bookings(message.from_user.id)
    if not bookings:
        await send_clean_message(message, "У тебя пока нет броней.", reply_markup=flow_keyboard())
        return
    lines = []
    for b in bookings:
        status = b["status"]
        reason = f" | причина: {b['cancel_reason']}" if b["cancel_reason"] else ""
        lines.append(
            f"Бронь #{b['id']} | trip #{b['trip_id']} | {b['start_title']} -> {b['end_title']} | "
            f"{format_trip_row(b)} | {b['price_rub']} руб | статус: {status}{reason}"
        )
    await send_flow_step(message, "\n".join(lines), cancel_booking_keyboard(bookings))


@router.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking_start(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import edit_or_send_clean

    booking_id = int(callback.data.split(":")[1])
    booking = repo.bookings.get_booking_for_cancel(callback.from_user.id, booking_id)
    if not booking:
        await callback.answer("Бронь не найдена.", show_alert=True)
        return
    if booking["status"] != "active":
        await callback.answer("Эту бронь уже нельзя отменить.", show_alert=True)
        return
    await state.update_data(booking_id=booking_id)
    await state.set_state(CancelBooking.waiting_reason)
    await edit_or_send_clean(callback, "Напиши причину отмены (она уйдёт водителю):")
    await callback.answer()


@router.message(CancelBooking.waiting_reason)
async def cancel_booking_reason(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import main_keyboard, send_clean_message

    reason = (message.text or "").strip()
    if len(reason) < 3:
        await send_clean_message(message, "Причина слишком короткая. Укажи подробнее.")
        return
    data = await state.get_data()
    booking_id_raw = data.get("booking_id")
    if booking_id_raw is None:
        await send_clean_message(
            message,
            "Сессия отмены брони устарела. Открой «Мои брони» и выбери отмену снова.",
            reply_markup=main_keyboard(repo, message.from_user.id),
        )
        await state.clear()
        return
    booking_id = int(booking_id_raw)
    try:
        trip_id_c, payload = repo.bookings.cancel_booking_by_passenger(message.from_user.id, booking_id, reason)
    except ValueError as exc:
        logger.info(
            "critical action=%s tg_user_id=%s booking_id=%s outcome=%s reason=%s",
            "cancel_booking_passenger",
            message.from_user.id,
            booking_id,
            "rejected",
            str(exc),
        )
        await send_clean_message(message, str(exc))
        await state.clear()
        return
    logger.info(
        "critical action=%s tg_user_id=%s booking_id=%s trip_id=%s outcome=%s",
        "cancel_booking_passenger",
        message.from_user.id,
        booking_id,
        trip_id_c,
        "success",
    )
    await state.clear()
    await send_clean_message(
        message, f"Бронь #{booking_id} отменена.", reply_markup=main_keyboard(repo, message.from_user.id)
    )
    try:
        await message.bot.send_message(
            payload["driver_tg_user_id"],
            (
                "Пассажир отменил бронь.\n"
                f"Trip #{payload['trip_id']} | {payload['start_title']} -> {payload['end_title']} | "
                f"{format_trip_when(payload.get('trip_date'), payload.get('departure_time'), payload.get('time_slot'))}\n"
                f"Причина: {payload['reason']}"
            ),
        )
    except Exception as err:
        logger.warning("Driver cancel notify failed: %s", err)
