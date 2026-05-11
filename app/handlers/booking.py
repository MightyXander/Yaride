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

FLOW_KIND_BOOKING = "booking"


@router.callback_query(F.data.startswith("book:"))
async def book_trip(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot_support import (
        add_favorite_keyboard,
        main_keyboard,
        send_post_flow_message,
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
    if callback.message:
        chat_id = callback.message.chat.id
        await send_post_flow_message(
            chat_id=chat_id,
            bot=callback.bot,
            text=f"Бронь #{booking_id} создана.\n\nДобавить этот маршрут в избранное?",
            inline_markup=add_favorite_keyboard(trip_id),
            reply_keyboard=main_keyboard(repo, callback.from_user.id),
        )
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
        close_flow,
        delete_user_message,
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
    bookings = repo.bookings.list_passenger_bookings(message.from_user.id)
    if not bookings:
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text="У тебя пока нет броней.",
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
        return
    lines = []
    for b in bookings:
        status = b["status"]
        reason = f" | причина: {b['cancel_reason']}" if b["cancel_reason"] else ""
        lines.append(
            f"Бронь #{b['id']} | trip #{b['trip_id']} | {b['start_title']} -> {b['end_title']} | "
            f"{format_trip_row(b)} | {b['price_rub']} руб | статус: {status}{reason}"
        )
    await open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND_BOOKING,
        text="\n".join(lines),
        inline_markup=with_back_button(cancel_booking_keyboard(bookings), target="menu"),
    )


@router.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking_start(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import flow_keyboard, update_flow

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
    if callback.message:
        await update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND_BOOKING,
            text="Напиши причину отмены (она уйдёт водителю):",
            inline_markup=None,
            reply_keyboard=flow_keyboard(),
        )
    await callback.answer()


@router.message(CancelBooking.waiting_reason)
async def cancel_booking_reason(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import (
        close_flow,
        delete_user_message,
        flow_keyboard,
        main_keyboard,
        send_post_flow_message,
        update_flow,
    )

    reason = (message.text or "").strip()
    await delete_user_message(message)
    if len(reason) < 3:
        await update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND_BOOKING,
            text="Причина слишком короткая. Укажи подробнее.",
            reply_keyboard=flow_keyboard(),
        )
        return
    data = await state.get_data()
    booking_id_raw = data.get("booking_id")
    if booking_id_raw is None:
        await state.clear()
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сессия отмены брони устарела. Открой «Мои брони» и выбери отмену снова.",
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
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
        await state.clear()
        await close_flow(chat_id=message.chat.id, bot=message.bot)
        await send_post_flow_message(
            chat_id=message.chat.id,
            bot=message.bot,
            text=str(exc),
            reply_keyboard=main_keyboard(repo, message.from_user.id),
        )
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
    await close_flow(chat_id=message.chat.id, bot=message.bot)
    await send_post_flow_message(
        chat_id=message.chat.id,
        bot=message.bot,
        text=f"Бронь #{booking_id} отменена.",
        reply_keyboard=main_keyboard(repo, message.from_user.id),
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
