"""Водитель: история поездок, «Управление», детали поездки, порог рейтинга, отклонение/отмена."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.chat_ui import ChatUiService
from app.formatting import effective_min_passenger_rating, format_trip_row, format_trip_when, passenger_rating_hint
from app.driver_access import is_approved_driver
from app.repo import Repo
from app.ui import KeyboardFactory

router = Router()
logger = logging.getLogger(__name__)

FLOW_KIND_MANAGE = "driver_manage"
FLOW_KIND_HISTORY = "driver_history"


def _mk(repo: Repo, keyboards: KeyboardFactory, tg_user_id: int):
    u = repo.users.get_user(tg_user_id)
    return keyboards.main_keyboard(is_driver=repo.users.is_active_driver(tg_user_id))


async def _require_driver(callback: CallbackQuery, repo: Repo):
    user = repo.users.get_user(callback.from_user.id)
    if not is_approved_driver(user):
        await callback.answer("Доступно только одобренным водителям.", show_alert=True)
        return None
    return user


def _manage_root_text(user_row) -> str:
    cur = effective_min_passenger_rating(
        user_row["min_passenger_rating"] if "min_passenger_rating" in user_row.keys() else None
    )
    if cur is not None:
        return (
            f"Авто-отказ новым броням: средний рейтинг пассажира ниже {float(cur):.1f} "
            f"(только если у него уже есть хотя бы одна оценка)."
        )
    return "Авто-фильтр по рейтингу выключен — новые пользователи без оценок всегда могут бронировать."


def _build_manage_root_markup(user_row, open_trips: list, keyboards: KeyboardFactory):
    """Корень «Управление»: либо клавиатура порога рейтинга (нет открытых), либо список поездок."""
    if not open_trips:
        inner = keyboards.driver_rating_threshold_keyboard()
        text = f"{_manage_root_text(user_row)}\n\nОткрытых поездок нет. Ниже можно задать порог рейтинга для будущих броней."
    else:
        inner = keyboards.driver_manage_root_keyboard(open_trips)
        text = f"{_manage_root_text(user_row)}\n\nОткрытые поездки — выбери для просмотра броней или отмены поездки:"
    return text, keyboards.with_back_button(inner, target="menu")


@router.message(F.text == "История поездок")
async def my_trips(
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
    trips = repo.trips.list_driver_trips(message.from_user.id)
    if not trips:
        await chat_ui.open_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND_HISTORY,
            text="У тебя пока нет созданных поездок.",
            inline_markup=keyboards.back_to_menu_keyboard(),
        )
        return
    lines = ["История поездок:"]
    for t in trips:
        free = t["seats_total"] - t["seats_booked"]
        lines.append(
            f"#{t['id']} | {t['start_title']} -> {t['end_title']} | {format_trip_row(t)} | "
            f"{t['price_rub']} руб | свободно {free}/{t['seats_total']} | {t['status']}"
        )
    await chat_ui.open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND_HISTORY,
        text="\n".join(lines),
        inline_markup=keyboards.back_to_menu_keyboard(),
    )


@router.message(F.text == "Управление")
async def driver_manage_entry(
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
    if not is_approved_driver(user):
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Раздел «Управление» доступен только одобренным водителям.",
            reply_keyboard=_mk(repo, keyboards, message.from_user.id),
        )
        return
    open_trips = [t for t in repo.trips.list_driver_trips(message.from_user.id) if t["status"] == "open"]
    text, markup = _build_manage_root_markup(user, open_trips, keyboards)
    await chat_ui.open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND_MANAGE,
        text=text,
        inline_markup=markup,
    )


@router.callback_query(F.data == "back:manage_root")
async def driver_manage_back_to_root(
    callback: CallbackQuery,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    """`back:manage_root` — возврат из детального экрана/подменю порога в корень «Управление»."""
    user = repo.users.get_user(callback.from_user.id)
    if not is_approved_driver(user):
        await callback.answer("Доступно только одобренным водителям.", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    open_trips = [t for t in repo.trips.list_driver_trips(callback.from_user.id) if t["status"] == "open"]
    text, markup = _build_manage_root_markup(user, open_trips, keyboards)
    await chat_ui.update_flow(
        chat_id=callback.message.chat.id,
        bot=callback.bot,
        flow_kind=FLOW_KIND_MANAGE,
        text=text,
        inline_markup=markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manage_trip:"))
async def driver_manage_trip_detail(
    callback: CallbackQuery,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    try:
        trip_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные.", show_alert=True)
        return
    if await _require_driver(callback, repo) is None:
        return
    trips = repo.trips.list_driver_trips(callback.from_user.id)
    trip = next((t for t in trips if int(t["id"]) == trip_id), None)
    if not trip or trip["status"] != "open":
        await callback.answer("Поездка недоступна.", show_alert=True)
        return
    bookings = repo.bookings.list_bookings_for_driver_trip(callback.from_user.id, trip_id)
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
            lines.append(f"— {b['passenger_name']}, рейтинг: {passenger_rating_hint(b)}")
    if callback.message:
        await chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND_MANAGE,
            text="\n".join(lines),
            inline_markup=keyboards.with_back_button(
                keyboards.driver_trip_detail_keyboard(trip_id, list(bookings)), target="manage_root"
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "thr_menu")
async def driver_thr_menu(
    callback: CallbackQuery,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    user = await _require_driver(callback, repo)
    if user is None:
        return
    cur = effective_min_passenger_rating(
        user["min_passenger_rating"] if "min_passenger_rating" in user.keys() else None
    )
    text_cur = (
        f"Сейчас: новая бронь отклоняется автоматически, если у пассажира уже есть оценки "
        f"и средний балл ниже {cur:.1f}."
        if cur is not None
        else "Сейчас: автоматический отказ по рейтингу выключен."
    )
    if callback.message:
        await chat_ui.update_flow(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            flow_kind=FLOW_KIND_MANAGE,
            text=f"{text_cur}\n\nБез ни одной оценки пассажир всё равно может забронировать место.",
            inline_markup=keyboards.with_back_button(
                keyboards.driver_rating_threshold_keyboard(), target="manage_root"
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("thr_set:"))
async def driver_thr_set(
    callback: CallbackQuery,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    if await _require_driver(callback, repo) is None:
        return
    raw = callback.data.split(":", 1)[1]
    try:
        if raw == "off":
            repo.users.set_driver_min_passenger_rating(callback.from_user.id, None)
        else:
            repo.users.set_driver_min_passenger_rating(callback.from_user.id, float(raw))
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if callback.message:
        await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
        await chat_ui.replace_with_notice(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            text="Настройка сохранена.",
            reply_keyboard=_mk(repo, keyboards, callback.from_user.id),
        )
    await callback.answer("Готово")


@router.callback_query(F.data.startswith("reject_bk:"))
async def driver_reject_booking(
    callback: CallbackQuery,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    try:
        booking_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    if await _require_driver(callback, repo) is None:
        return
    try:
        payload = repo.bookings.reject_booking_by_driver(callback.from_user.id, booking_id)
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
    if callback.message:
        await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
        await chat_ui.replace_with_notice(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            text="Бронь отклонена, место снова доступно.",
            reply_keyboard=_mk(repo, keyboards, callback.from_user.id),
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
async def driver_cancel_trip(
    callback: CallbackQuery,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    try:
        trip_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    if await _require_driver(callback, repo) is None:
        return
    try:
        passenger_tg_ids = repo.trips.cancel_trip_by_driver(callback.from_user.id, trip_id)
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
    if callback.message:
        await chat_ui.close_flow(chat_id=callback.message.chat.id, bot=callback.bot)
        await chat_ui.replace_with_notice(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            text=f"Поездка #{trip_id} отменена. Пассажиры с активной бронью уведомлены.",
            reply_keyboard=_mk(repo, keyboards, callback.from_user.id),
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
