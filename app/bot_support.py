"""Сборка UI-помощников, оркестратора маршрута и навигации (не точка входа процесса)."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)

from app.bootstrap import Container
from app.chat_ui import UNSET, ChatUiService
from app.flow_mode_cfg import FLOW_MODE_CFG
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

STALE_CREATE_FLOW = "Сессия создания поездки устарела (часто это старая кнопка). Начни заново: «Создать поездку»."
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


# ── клавиатуры (тонкие обёртки над KeyboardFactory) ────────────────────────


def main_keyboard(repo: Repo, tg_user_id: int) -> ReplyKeyboardMarkup:
    user = repo.users.get_user(tg_user_id)
    is_driver = user is not None and user["role"] == "driver"
    return _ctx().keyboards.main_keyboard(is_driver=is_driver)


def flow_keyboard() -> ReplyKeyboardMarkup:
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


def with_back_button(markup: InlineKeyboardMarkup, target: str = "menu") -> InlineKeyboardMarkup:
    return _ctx().keyboards.with_back_button(markup, target)


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


def location_reply_keyboard() -> ReplyKeyboardMarkup:
    return _ctx().keyboards.location_reply_keyboard()


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


# ── anchor API: тонкие обёртки над ChatUiService ───────────────────────────


def chat_ui() -> ChatUiService:
    return _ctx().chat_ui


async def open_flow(
    *,
    chat_id: int,
    bot: Bot,
    flow_kind: str,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    reply_keyboard: ReplyKeyboardMarkup | None = None,
    reply_hint: str = "Кнопки навигации ниже:",
) -> int:
    return await chat_ui().open_flow(
        chat_id=chat_id,
        bot=bot,
        flow_kind=flow_kind,
        text=text,
        inline_markup=inline_markup,
        reply_keyboard=reply_keyboard,
        reply_hint=reply_hint,
    )


async def update_flow(
    *,
    chat_id: int,
    bot: Bot,
    flow_kind: str,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    reply_keyboard=UNSET,
    reply_hint: str = "Кнопки навигации ниже:",
) -> int:
    return await chat_ui().update_flow(
        chat_id=chat_id,
        bot=bot,
        flow_kind=flow_kind,
        text=text,
        inline_markup=inline_markup,
        reply_keyboard=reply_keyboard,
        reply_hint=reply_hint,
    )


async def close_flow(*, chat_id: int, bot: Bot, keep_message_id: int | None = None) -> None:
    await chat_ui().close_flow(chat_id=chat_id, bot=bot, keep_message_id=keep_message_id)


async def send_post_flow_message(
    *,
    chat_id: int,
    bot: Bot,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    reply_keyboard: ReplyKeyboardMarkup | None = None,
    reply_hint: str = "Главное меню:",
) -> int:
    """Одиночное «notice»-сообщение: предыдущее notice (или любой anchor) заменяется.

    Следующий обычный `open_flow` удалит этот notice автоматически —
    «Поездка создана / отменена / нет избранных» больше не накапливаются в чате.
    """
    return await chat_ui().replace_with_notice(
        chat_id=chat_id,
        bot=bot,
        text=text,
        inline_markup=inline_markup,
        reply_keyboard=reply_keyboard,
        reply_hint=reply_hint,
    )


async def delete_user_message(message: Message) -> None:
    await chat_ui().delete_user_message(message)


# ── гео-подсказки на шаге выбора отправления ───────────────────────────────


async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, Exception):
        pass


async def _send_or_edit_geo_suggestions(
    message: Message,
    prev_mid: int | None,
    text: str,
    markup: InlineKeyboardMarkup,
) -> int:
    """Отдельное сообщение «Ближайшие остановки» (не anchor): edit при наличии, иначе send."""
    bot = message.bot
    chat_id = message.chat.id
    if prev_mid is not None:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=prev_mid, text=text, reply_markup=markup)
            return prev_mid
        except TelegramBadRequest:
            await _safe_delete_message(bot, chat_id, prev_mid)
    sent = await message.answer(text, reply_markup=markup)
    return sent.message_id


def configure(container: Container) -> tuple[TripFlowOrchestrator, NavigationFlow]:
    """Инициализирует модуль после сборки контейнера; возвращает flow и nav для диспетчера."""
    global _c, FLOW_ORCHESTRATOR, NAVIGATION_FLOW
    _c = container

    orch = TripFlowOrchestrator(
        mode_cfg=FLOW_MODE_CFG,
        chat_ui=container.chat_ui,
        add_back_button=add_back_button,
        localities_keyboard=localities_keyboard,
        districts_keyboard=districts_keyboard,
        stops_keyboard=stops_keyboard,
        location_reply_keyboard=location_reply_keyboard,
        trip_calendar_factory=trip_calendar,
    )

    nav = NavigationFlow(
        registration_state=Registration,
        trip_search_state=TripSearch,
        trip_create_state=TripCreate,
        chat_ui=container.chat_ui,
        main_keyboard=main_keyboard,
        role_switch_keyboard=role_switch_keyboard,
        add_back_button=add_back_button,
        localities_keyboard=localities_keyboard,
        districts_keyboard=districts_keyboard,
        stops_keyboard=stops_keyboard,
        time_keyboard=time_keyboard,
        seats_keyboard=seats_keyboard,
        trip_calendar_factory=trip_calendar,
        mode_cfg=FLOW_MODE_CFG,
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
    """Геолокация на шаге выбора отправления: показать топ остановок или перейти к району."""
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
    ranked = repo.routes.nearest_stops_global(lat, lng, limit=st.geo_suggest_limit, max_km=st.geo_suggest_max_km)
    if ranked:
        txt = (
            "Ближайшие остановки посадки к твоей точке (км по прямой до точки остановки в каталоге, не время в пути). "
            "Выбери кнопку ниже или продолжи выбор населённого пункта кнопками в сообщении выше."
        )
        mid = await _send_or_edit_geo_suggestions(
            message, prev_mid, txt, geo_suggested_start_stops_keyboard(ranked, mode)
        )
        await state.update_data(**{GEO_SUGGEST_MESSAGE_KEY: mid})
        return

    if prev_mid is not None:
        await _safe_delete_message(message.bot, message.chat.id, prev_mid)
    await state.update_data(**{GEO_SUGGEST_MESSAGE_KEY: None})

    resolved = repo.routes.nearest_locality_from_geo(lat, lng, max_km=st.locality_geo_max_km)
    if not resolved:
        try:
            await message.answer(
                "Не удалось подобрать остановки или город по координатам (слишком далеко или нет данных). "
                "Выбери город из списка."
            )
        except Exception:
            pass
        return
    locality, _dkm = resolved
    await delete_tracked_user_geo_messages(message.bot, message.chat.id, state)
    await FLOW_ORCHESTRATOR.apply_start_locality_from_geo(message, state, repo, mode, locality)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


async def push_main_menu_after_restart(bot: Bot, repo: Repo) -> None:
    """После рестарта рассылаем главное меню, чтобы сменить reply-клавиатуру."""
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
            await bot.send_message(
                tg_user_id,
                text,
                reply_markup=main_keyboard(repo, tg_user_id),
                disable_notification=True,
            )
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


def stale_flow_text(mode: str) -> str:
    return STALE_SEARCH_FLOW if mode == "search" else STALE_CREATE_FLOW
