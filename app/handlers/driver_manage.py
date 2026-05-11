"""Водитель: история поездок, «Управление», детали поездки, порог рейтинга, отклонение/отмена."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.formatting import format_trip_row, format_trip_when
from app.repo import Repo

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "История поездок")
async def my_trips(message: Message, repo: Repo) -> None:
    from app.bot import send_clean_message

    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    trips = repo.list_driver_trips(message.from_user.id)
    if not trips:
        await send_clean_message(message, "У тебя пока нет созданных поездок.")
        return
    lines = ["История поездок:"]
    for t in trips:
        free = t["seats_total"] - t["seats_booked"]
        lines.append(
            f"#{t['id']} | {t['start_title']} -> {t['end_title']} | {format_trip_row(t)} | "
            f"{t['price_rub']} руб | свободно {free}/{t['seats_total']} | {t['status']}"
        )
    await send_clean_message(message, "\n".join(lines))


@router.message(F.text == "Управление")
async def driver_manage_entry(message: Message, repo: Repo) -> None:
    from app.bot import (
        driver_manage_root_keyboard,
        driver_rating_threshold_keyboard,
        send_clean_message,
    )

    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    if user["role"] != "driver":
        await send_clean_message(message, "Раздел «Управление» только для водителей.")
        return
    open_trips = [t for t in repo.list_driver_trips(message.from_user.id) if t["status"] == "open"]
    cur = user["min_passenger_rating"] if "min_passenger_rating" in user.keys() else None
    thr_line = (
        f"Авто-отказ новым броням: средний рейтинг пассажира ниже {float(cur):.1f} "
        f"(только если у него уже есть хотя бы одна оценка)."
        if cur is not None and float(cur) > 0
        else "Авто-фильтр по рейтингу выключен — новые пользователи без оценок всегда могут бронировать."
    )
    if not open_trips:
        await send_clean_message(
            message,
            f"{thr_line}\n\nОткрытых поездок нет. Ниже можно задать порог рейтинга для будущих броней.",
            reply_markup=driver_rating_threshold_keyboard(),
        )
        return
    await send_clean_message(
        message,
        f"{thr_line}\n\nОткрытые поездки — выбери для просмотра броней или отмены поездки:",
        reply_markup=driver_manage_root_keyboard(open_trips),
    )


@router.callback_query(F.data.startswith("manage_trip:"))
async def driver_manage_trip_detail(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot import (
        _passenger_rating_hint,
        driver_trip_detail_keyboard,
        edit_or_send_clean,
    )

    try:
        trip_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные.", show_alert=True)
        return
    user = repo.get_user(callback.from_user.id)
    if not user or user["role"] != "driver":
        await callback.answer("Только для водителя.", show_alert=True)
        return
    trips = repo.list_driver_trips(callback.from_user.id)
    trip = next((t for t in trips if int(t["id"]) == trip_id), None)
    if not trip or trip["status"] != "open":
        await callback.answer("Поездка недоступна.", show_alert=True)
        return
    bookings = repo.list_bookings_for_driver_trip(callback.from_user.id, trip_id)
    free = int(trip["seats_total"]) - int(trip["seats_booked"])
    lines = [
        f"Поездка #{trip_id}: {trip['start_title']} → {trip['end_title']}",
        format_trip_when(trip["trip_date"], trip["departure_time"], trip["time_slot"]),
        f"{trip['price_rub']} руб | свободно {free}/{trip['seats_total']}",
        "",
        "Активные брони:",
    ]
    if not bookings:
        lines.append("пока никто не забронировал.")
    else:
        for b in bookings:
            lines.append(f"— {b['passenger_name']}, рейтинг: {_passenger_rating_hint(b)}")
    await edit_or_send_clean(
        callback,
        "\n".join(lines),
        reply_markup=driver_trip_detail_keyboard(trip_id, list(bookings)),
    )
    await callback.answer()


@router.callback_query(F.data == "thr_menu")
async def driver_thr_menu(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot import driver_rating_threshold_keyboard, edit_or_send_clean

    user = repo.get_user(callback.from_user.id)
    if not user or user["role"] != "driver":
        await callback.answer("Только для водителя.", show_alert=True)
        return
    cur = user["min_passenger_rating"] if "min_passenger_rating" in user.keys() else None
    text_cur = (
        f"Сейчас: новая бронь отклоняется автоматически, если у пассажира уже есть оценки "
        f"и средний балл ниже {float(cur):.1f}."
        if cur is not None and float(cur) > 0
        else "Сейчас: автоматический отказ по рейтингу выключен."
    )
    await edit_or_send_clean(
        callback,
        f"{text_cur}\n\nБез ни одной оценки пассажир всё равно может забронировать место.",
        reply_markup=driver_rating_threshold_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("thr_set:"))
async def driver_thr_set(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot import edit_or_send_clean, main_keyboard

    user = repo.get_user(callback.from_user.id)
    if not user or user["role"] != "driver":
        await callback.answer("Только для водителя.", show_alert=True)
        return
    raw = callback.data.split(":", 1)[1]
    try:
        if raw == "off":
            repo.set_driver_min_passenger_rating(callback.from_user.id, None)
        else:
            repo.set_driver_min_passenger_rating(callback.from_user.id, float(raw))
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await edit_or_send_clean(callback, "Настройка сохранена.", reply_markup=main_keyboard(repo, callback.from_user.id))
    await callback.answer("Готово")


@router.callback_query(F.data.startswith("reject_bk:"))
async def driver_reject_booking(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot import edit_or_send_clean, main_keyboard

    try:
        booking_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    user = repo.get_user(callback.from_user.id)
    if not user or user["role"] != "driver":
        await callback.answer("Только для водителя.", show_alert=True)
        return
    try:
        payload = repo.reject_booking_by_driver(callback.from_user.id, booking_id)
    except ValueError as exc:
        logger.info(
            "critical action=%s tg_user_id=%s booking_id=%s outcome=%s reason=%s",
            "reject_booking_driver",
            callback.from_user.id,
            booking_id,
            "rejected",
            str(exc),
        )
        await callback.answer(str(exc), show_alert=True)
        return
    logger.info(
        "critical action=%s tg_user_id=%s booking_id=%s trip_id=%s outcome=%s",
        "reject_booking_driver",
        callback.from_user.id,
        booking_id,
        int(payload["trip_id"]),
        "success",
    )
    await edit_or_send_clean(
        callback, "Бронь отклонена, место снова доступно.", reply_markup=main_keyboard(repo, callback.from_user.id)
    )
    await callback.answer("Отклонено")
    try:
        await callback.bot.send_message(
            int(payload["passenger_tg_user_id"]),
            (
                "Водитель отклонил твою бронь.\n"
                f"Trip #{payload['trip_id']} | {payload['start_title']} → {payload['end_title']} | "
                f"{format_trip_when(payload.get('trip_date'), payload.get('departure_time'), payload.get('time_slot'))}"
            ),
        )
    except Exception as err:
        logger.warning("Passenger notify reject: %s", err)


@router.callback_query(F.data.startswith("cancel_trip:"))
async def driver_cancel_trip(callback: CallbackQuery, repo: Repo) -> None:
    from app.bot import edit_or_send_clean, main_keyboard

    try:
        trip_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    user = repo.get_user(callback.from_user.id)
    if not user or user["role"] != "driver":
        await callback.answer("Только для водителя.", show_alert=True)
        return
    try:
        passenger_tg_ids = repo.cancel_trip_by_driver(callback.from_user.id, trip_id)
    except ValueError as exc:
        logger.info(
            "critical action=%s tg_user_id=%s trip_id=%s outcome=%s reason=%s",
            "cancel_trip_driver",
            callback.from_user.id,
            trip_id,
            "rejected",
            str(exc),
        )
        await callback.answer(str(exc), show_alert=True)
        return
    logger.info(
        "critical action=%s tg_user_id=%s trip_id=%s outcome=%s passengers_notified=%s",
        "cancel_trip_driver",
        callback.from_user.id,
        trip_id,
        "success",
        len(passenger_tg_ids),
    )
    await edit_or_send_clean(
        callback,
        f"Поездка #{trip_id} отменена. Пассажиры с активной бронью уведомлены.",
        reply_markup=main_keyboard(repo, callback.from_user.id),
    )
    await callback.answer("Поездка отменена")
    for tg_uid in passenger_tg_ids:
        try:
            await callback.bot.send_message(
                tg_uid,
                f"Водитель отменил поездку #{trip_id}. Твоя бронь аннулирована.",
            )
        except Exception as err:
            logger.warning("Passenger notify cancel trip: %s", err)
