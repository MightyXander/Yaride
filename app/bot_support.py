"""Сборка UI-хелперов, оркестратора маршрута и навигации (не точка входа процесса)."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.bootstrap import Container
from app.navigation_flow import NavigationFlow
from app.repo import Repo
from app.states import Registration, TripCreate, TripSearch
from app.trip_flow import (
    GEO_USER_LOCATION_IDS_KEY,
    TripFlowOrchestrator,
    delete_tracked_user_geo_messages,
)
from app.yaride_calendar import trip_calendar

logger = logging.getLogger(__name__)

STALE_CREATE_FLOW = (
    "Сессия создания поездки устарела (часто это старая кнопка). Начни заново: «Создать поездку»."
)
STALE_SEARCH_FLOW = "Сессия поиска устарела. Начни заново: «Найти поездки»."

_c: Container | None = None

FLOW_ORCHESTRATOR: TripFlowOrchestrator | None = None
NAVIGATION_FLOW: NavigationFlow | None = None

GEO_SUGGEST_MESSAGE_KEY = "geo_suggest_message_id"


def _ctx() -> Container:
    if _c is None:
        raise RuntimeError("bot_support.configure() must run before using Telegram helpers.")
    return _c


def _active_settings():
    return _ctx().settings


def main_keyboard(repo: Repo, tg_user_id: int) -> ReplyKeyboardMarkup:
    user = repo.users.get_user(tg_user_id)
    is_driver = user is not None and user["role"] == "driver"
    return _ctx().keyboards.main_keyboard(is_driver=is_driver)


def flow_keyboard():
    return _ctx().keyboards.flow_keyboard()


def role_keyboard() -> InlineKeyboardMarkup:
    return _ctx().keyboards.role_keyboard()


def role_switch_keyboard(current_role: str) -> InlineKeyboardMarkup:
    return _ctx().keyboards.role_switch_keyboard(current_role)


def stops_keyboard(stops: list, prefix: str) -> InlineKeyboardMarkup:
    return _ctx().keyboards.stops_keyboard(stops, prefix)


def localities_keyboard(prefix: str, localities: list[str]) -> InlineKeyboardMarkup:
    return _ctx().keyboards.localities_keyboard(prefix, localities)


def districts_keyboard(prefix: str, districts: list[str]) -> InlineKeyboardMarkup:
    return _ctx().keyboards.districts_keyboard(prefix, districts)


def add_back_button(markup: InlineKeyboardMarkup, back_callback: str) -> InlineKeyboardMarkup:
    return _ctx().keyboards.add_back_button(markup, back_callback)


def time_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return _ctx().keyboards.time_keyboard(prefix)


def seats_keyboard(prefix: str = "create_seats") -> InlineKeyboardMarkup:
    return _ctx().keyboards.seats_keyboard(prefix)


def price_keyboard(prefix: str = "create_price") -> InlineKeyboardMarkup:
    return _ctx().keyboards.price_keyboard(prefix)


def trips_keyboard(trips: list) -> InlineKeyboardMarkup:
    return _ctx().keyboards.trips_keyboard(trips)


def cancel_booking_keyboard(bookings: list) -> InlineKeyboardMarkup:
    return _ctx().keyboards.cancel_booking_keyboard(bookings)


def driver_manage_root_keyboard(open_trips: list) -> InlineKeyboardMarkup:
    return _ctx().keyboards.driver_manage_root_keyboard(open_trips)


def driver_trip_detail_keyboard(trip_id: int, bookings: list) -> InlineKeyboardMarkup:
    return _ctx().keyboards.driver_trip_detail_keyboard(trip_id, bookings)


def driver_rating_threshold_keyboard() -> InlineKeyboardMarkup:
    return _ctx().keyboards.driver_rating_threshold_keyboard()


def favorite_routes_keyboard(rows: list) -> InlineKeyboardMarkup:
    return _ctx().keyboards.favorite_routes_keyboard(rows)


def add_favorite_keyboard(trip_id: int) -> InlineKeyboardMarkup:
    return _ctx().keyboards.add_favorite_keyboard(trip_id)


def geo_suggested_start_stops_keyboard(ranked: list[tuple[sqlite3.Row, float]], mode: str) -> InlineKeyboardMarkup:
    return _ctx().keyboards.geo_suggested_start_stops_keyboard(ranked, mode)


def account_kb_menu(show_become_driver: bool) -> InlineKeyboardMarkup:
    return _ctx().keyboards.account_menu_keyboard(show_become_driver=show_become_driver)


def account_kb_back() -> InlineKeyboardMarkup:
    return _ctx().keyboards.account_back_keyboard()


def _passenger_rating_hint(row) -> str:
    rc = int(row["rating_count"] or 0)
    ra = float(row["rating_avg"] or 0.0)
    if rc == 0:
        return "нет оценок"
    return f"{ra:.1f}, оценок: {rc}"


async def track_bot_message(message: Message) -> None:
    await _ctx().chat_ui.track_bot_message(message)


async def send_clean_message(message: Message, text: str, **kwargs) -> Message:
    return await _ctx().chat_ui.send_clean_message(message, text, **kwargs)


async def send_flow_step(message: Message, text: str, inline_markup: InlineKeyboardMarkup) -> None:
    await _ctx().chat_ui.send_flow_step(message, text, inline_markup)


async def edit_or_send_clean(callback: CallbackQuery, text: str, **kwargs) -> None:
    await _ctx().chat_ui.edit_or_send_clean(callback, text, **kwargs)


async def cleanup_chat(message: Message) -> int | None:
    return await _ctx().chat_ui.cleanup_chat(message)


async def drop_empty_chat_bridge(message: Message, bridge_id: int | None) -> None:
    await _ctx().chat_ui.drop_empty_chat_bridge(message, bridge_id)


async def _delete_message_safe(chat_id: int, message_id: int, bot) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass


async def _send_or_edit_geo_suggestions(
    message: Message,
    prev_mid: int | None,
    text: str,
    markup: InlineKeyboardMarkup,
) -> int:
    bot = message.bot
    chat_id = message.chat.id
    if prev_mid is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=prev_mid,
                text=text,
                reply_markup=markup,
            )
            return prev_mid
        except TelegramBadRequest:
            await _delete_message_safe(chat_id, prev_mid, bot)
    sent = await message.answer(text, reply_markup=markup)
    await track_bot_message(sent)
    return sent.message_id


async def reply_stop_step_after_location(message: Message, text: str, markup: InlineKeyboardMarkup) -> None:
    await message.answer("\u2060", reply_markup=ReplyKeyboardRemove())
    sent = await message.answer(text, reply_markup=markup)
    await track_bot_message(sent)


async def hint_start_locality_geo(message: Message, mode: str) -> None:
    _ = mode
    sent = await message.answer(
        "📍 Отправь геолокацию — покажем ближайшие остановки посадки (или выбери город из списка выше).",
        reply_markup=_ctx().keyboards.location_reply_keyboard(),
    )
    await track_bot_message(sent)


FLOW_MODE_CFG = {
    "search": {
        "state_group": TripSearch,
        "start_locality_prefix": "Sfl",
        "start_district_prefix": "Sfd",
        "start_admin_prefix": "Sfa",
        "start_stop_prefix": "Sfp",
        "end_locality_prefix": "Stl",
        "end_district_prefix": "Std",
        "end_admin_prefix": "Sta",
        "end_stop_prefix": "Stp",
        "start_locality_back": "search_start_locality",
        "start_district_back": "search_start_district",
        "start_admin_back": "search_start_admin",
        "start_stop_back": "search_start_stop",
        "end_locality_back": "search_end_locality",
        "end_district_back": "search_end_district",
        "end_admin_back": "search_end_admin",
        "end_stop_back": "search_end_stop",
        "entry_text": "Откуда едем: выбери населённый пункт или город:",
        "end_entry_text": "Куда едем: выбери населённый пункт или город:",
    },
    "create": {
        "state_group": TripCreate,
        "start_locality_prefix": "Cfl",
        "start_district_prefix": "Cfd",
        "start_admin_prefix": "Cfa",
        "start_stop_prefix": "Cfp",
        "end_locality_prefix": "Ctl",
        "end_district_prefix": "Ctd",
        "end_admin_prefix": "Cta",
        "end_stop_prefix": "Ctp",
        "start_locality_back": "create_start_locality",
        "start_district_back": "create_start_district",
        "start_admin_back": "create_start_admin",
        "start_stop_back": "create_start_stop",
        "end_locality_back": "create_end_locality",
        "end_district_back": "create_end_district",
        "end_admin_back": "create_end_admin",
        "end_stop_back": "create_end_stop",
        "entry_text": "Старт поездки: выбери населённый пункт или город:",
        "end_entry_text": "Финиш поездки: выбери населённый пункт или город:",
    },
}


def configure(container: Container) -> tuple[TripFlowOrchestrator, NavigationFlow]:
    """Инициализирует модуль после сборки контейнера; возвращает flow и nav для диспетчера."""
    global _c, FLOW_ORCHESTRATOR, NAVIGATION_FLOW
    _c = container

    orch = TripFlowOrchestrator(
        mode_cfg=FLOW_MODE_CFG,
        send_flow_step=send_flow_step,
        edit_or_send_clean=edit_or_send_clean,
        add_back_button=add_back_button,
        localities_keyboard=localities_keyboard,
        districts_keyboard=districts_keyboard,
        stops_keyboard=stops_keyboard,
        trip_calendar_factory=trip_calendar,
        reply_stop_step_message=reply_stop_step_after_location,
        on_begin_start_locality_shown=hint_start_locality_geo,
    )

    nav = NavigationFlow(
        registration_state=Registration,
        trip_search_state=TripSearch,
        trip_create_state=TripCreate,
        edit_or_send_clean=edit_or_send_clean,
        send_flow_step=send_flow_step,
        send_clean_message=send_clean_message,
        main_keyboard=main_keyboard,
        role_switch_keyboard=role_switch_keyboard,
        add_back_button=add_back_button,
        localities_keyboard=localities_keyboard,
        districts_keyboard=districts_keyboard,
        stops_keyboard=stops_keyboard,
        time_keyboard=time_keyboard,
        seats_keyboard=seats_keyboard,
        trip_calendar_factory=trip_calendar,
    )
    FLOW_ORCHESTRATOR = orch
    NAVIGATION_FLOW = nav
    return orch, nav


async def _handle_start_locality_geo(
    message: Message,
    state: FSMContext,
    repo: Repo,
    *,
    mode: str,
) -> None:
    assert FLOW_ORCHESTRATOR is not None
    loc = message.location
    if loc is None:
        return
    lat = float(loc.latitude)
    lng = float(loc.longitude)
    data = await state.get_data()
    prev_mid_raw = data.get(GEO_SUGGEST_MESSAGE_KEY)
    prev_mid: int | None = int(prev_mid_raw) if prev_mid_raw is not None else None
    loc_ids = list(data.get(GEO_USER_LOCATION_IDS_KEY) or [])
    loc_ids.append(message.message_id)
    await state.update_data(**{GEO_USER_LOCATION_IDS_KEY: loc_ids})

    st = _active_settings()
    ranked = repo.routes.nearest_stops_global(
        lat,
        lng,
        limit=st.geo_suggest_limit,
        max_km=st.geo_suggest_max_km,
    )
    if ranked:
        txt = (
            "Ближайшие остановки посадки к твоей точке (км по прямой до точки остановки в каталоге, не время в пути). "
            "Выбери кнопку ниже или продолжи выбор населённого пункта кнопками в сообщении выше."
        )
        mid = await _send_or_edit_geo_suggestions(
            message,
            prev_mid,
            txt,
            geo_suggested_start_stops_keyboard(ranked, mode),
        )
        await state.update_data(**{GEO_SUGGEST_MESSAGE_KEY: mid})
        return

    if prev_mid is not None:
        await _delete_message_safe(message.chat.id, prev_mid, message.bot)
    await state.update_data(**{GEO_SUGGEST_MESSAGE_KEY: None})

    resolved = repo.routes.nearest_locality_from_geo(lat, lng, max_km=st.locality_geo_max_km)
    if not resolved:
        sent_err = await message.answer(
            "Не удалось подобрать остановки или город по координатам (слишком далеко или нет данных). Выбери город из списка.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await track_bot_message(sent_err)
        return
    locality, dkm = resolved
    sent_loc = await message.answer(
        f"Населённый пункт отправления: «{locality}» (~{dkm:.1f} км). Выбери район на следующем шаге.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await track_bot_message(sent_loc)
    await delete_tracked_user_geo_messages(message.bot, message.chat.id, state)
    await FLOW_ORCHESTRATOR.apply_start_locality_from_geo(message, state, repo, mode, locality)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


async def push_main_menu_after_restart(bot: Bot, repo: Repo) -> None:
    """После рестарта FSM в памяти пуст; рассылаем главное меню, чтобы сменить reply-клавиатуру."""
    if not _env_bool("YARIDE_PUSH_MENU_ON_START", True):
        logger.info("Меню после рестарта отключено (YARIDE_PUSH_MENU_ON_START)")
        return
    ids = repo.users.list_all_tg_user_ids()
    if not ids:
        return
    text = "Бот перезапущен — сценарии сброшены. Продолжайте с главного меню ниже."
    ok = skip = 0
    for tg_user_id in ids:
        try:
            sent = await bot.send_message(
                tg_user_id,
                text,
                reply_markup=main_keyboard(repo, tg_user_id),
                disable_notification=True,
            )
            await track_bot_message(sent)
            ok += 1
        except TelegramForbiddenError:
            skip += 1
        except TelegramBadRequest as exc:
            msg = str(exc).lower()
            if "blocked" in msg or "chat not found" in msg or "user is deactivated" in msg:
                skip += 1
            else:
                logger.warning("Меню после рестарта: tg=%s — %s", tg_user_id, exc)
        except Exception:
            logger.exception("Меню после рестарта: tg=%s", tg_user_id)
        await asyncio.sleep(0.04)
    logger.info(
        "После рестарта главное меню отправлено %s из %s пользователей (пропусков: %s)",
        ok,
        len(ids),
        skip,
    )
