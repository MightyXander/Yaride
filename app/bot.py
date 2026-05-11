from __future__ import annotations

import asyncio
import calendar
import logging
import os
import sqlite3
from datetime import date as date_cls
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram_calendar.schemas import SimpleCalAct

from app.bootstrap import attach_to_dispatcher, build_container
from app.chat_ui import ChatUiService
from app.config import Settings
from app.formatting import format_trip_row
from app.handlers.account import router as account_router
from app.handlers.booking import router as booking_router
from app.handlers.driver_manage import router as driver_manage_router
from app.handlers.favorites import router as favorites_router
from app.handlers.rating import router as rating_router
from app.handlers.registration import router as registration_router
from app.handlers.trip_create import router as trip_create_router
from app.handlers.trip_search import router as trip_search_router
from app.navigation_flow import NavigationFlow
from app.rating_worker import process_pending_rating_prompts
from app.repo import Repo
from app.states import Registration, TripCreate, TripSearch
from app.trip_flow import (
    GEO_USER_LOCATION_IDS_KEY,
    TripFlowOrchestrator,
    delete_tracked_user_geo_messages,
)
from app.ui import KeyboardFactory

logger = logging.getLogger(__name__)
router = Router()

# Устаревшие inline-кнопки при пустом FSM
STALE_CREATE_FLOW = "Сессия создания поездки устарела (часто это старая кнопка). Начни заново: «Создать поездку»."
STALE_SEARCH_FLOW = "Сессия поиска устарела. Начни заново: «Найти поездки»."


class YarideCalendar(SimpleCalendar):
    """Календарь с русскими подсказками при выходе за допустимый диапазон дат."""

    async def start_calendar(
        self,
        year: int = datetime.now().year,
        month: int = datetime.now().month,
    ) -> InlineKeyboardMarkup:
        """Календарь, где прошедшие даты скрыты (пустые ячейки)."""
        today = datetime.now()
        now_weekday = self._labels.days_of_week[today.weekday()]
        now_month, now_year, now_day = today.month, today.year, today.day

        def is_out_of_range(day_num: int) -> bool:
            date_to_check = datetime(year, month, day_num)
            if self.min_date and date_to_check < self.min_date:
                return True
            if self.max_date and date_to_check > self.max_date:
                return True
            return False

        def highlight_month() -> str:
            month_str = self._labels.months[month - 1]
            if now_month == month and now_year == year:
                return f"[{month_str}]"
            return month_str

        # Дни недели оставляем как в upstream.
        def weekday_label(weekday: str) -> str:
            if now_month == month and now_year == year and now_weekday == weekday:
                return f"[{weekday}]"
            return weekday

        kb: list[list[InlineKeyboardButton]] = []

        years_row = [
            InlineKeyboardButton(
                text="<<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_y, year=year, month=month, day=1).pack(),
            ),
            InlineKeyboardButton(
                text=str(year) if year != now_year else f"[{year}]",
                callback_data=self.ignore_callback,
            ),
            InlineKeyboardButton(
                text=">>",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_y, year=year, month=month, day=1).pack(),
            ),
        ]
        kb.append(years_row)

        month_row = [
            InlineKeyboardButton(
                text="<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_m, year=year, month=month, day=1).pack(),
            ),
            InlineKeyboardButton(
                text=highlight_month(),
                callback_data=self.ignore_callback,
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_m, year=year, month=month, day=1).pack(),
            ),
        ]
        kb.append(month_row)

        week_days_labels_row: list[InlineKeyboardButton] = []
        for weekday in self._labels.days_of_week:
            week_days_labels_row.append(
                InlineKeyboardButton(text=weekday_label(weekday), callback_data=self.ignore_callback)
            )
        kb.append(week_days_labels_row)

        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            days_row: list[InlineKeyboardButton] = []
            for day in week:
                if day == 0:
                    days_row.append(InlineKeyboardButton(text=" ", callback_data=self.ignore_callback))
                    continue
                if is_out_of_range(day):
                    # Прошедшие/недоступные даты: без цифры и без клика.
                    days_row.append(InlineKeyboardButton(text=" ", callback_data=self.ignore_callback))
                    continue

                day_text = str(day)
                if now_month == month and now_year == year and now_day == day:
                    day_text = f"[{day_text}]"
                days_row.append(
                    InlineKeyboardButton(
                        text=day_text,
                        callback_data=SimpleCalendarCallback(
                            act=SimpleCalAct.day, year=year, month=month, day=day
                        ).pack(),
                    )
                )
            kb.append(days_row)

        cancel_row = [
            InlineKeyboardButton(
                text=self._labels.cancel_caption,
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.cancel, year=year, month=month, day=1).pack(),
            ),
            InlineKeyboardButton(text=" ", callback_data=self.ignore_callback),
            InlineKeyboardButton(
                text=self._labels.today_caption,
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.today, year=year, month=month, day=1).pack(),
            ),
        ]
        kb.append(cancel_row)
        return InlineKeyboardMarkup(row_width=7, inline_keyboard=kb)

    async def process_selection(self, query: CallbackQuery, data: SimpleCalendarCallback) -> tuple:
        # В upstream при открытом текущем месяце «Сегодня» только делает query.answer() без эффекта.
        if data.act == SimpleCalAct.today:
            now = datetime.now()
            day_data = SimpleCalendarCallback(
                act=SimpleCalAct.day,
                year=now.year,
                month=now.month,
                day=now.day,
            )
            return await self.process_day_select(day_data, query)
        return await super().process_selection(query, data)

    async def process_day_select(self, data, query):
        picked = datetime(int(data.year), int(data.month), int(data.day))
        if self.min_date and self.min_date > picked:
            await query.answer(
                f"Нельзя выбрать прошедшую дату. Доступно с {self.min_date.strftime('%d.%m.%Y')}.",
                show_alert=self.show_alerts,
            )
            return False, None
        if self.max_date and self.max_date < picked:
            await query.answer(
                f"Выберите дату не позже {self.max_date.strftime('%d.%m.%Y')}.",
                show_alert=self.show_alerts,
            )
            return False, None
        await query.message.delete_reply_markup()
        return True, picked


def trip_calendar() -> YarideCalendar:
    """Календарь без прошедших дат (с сегодняшнего дня)."""
    cal = YarideCalendar(
        locale="ru_RU",
        show_alerts=True,
        cancel_btn="Отмена",
        today_btn="Сегодня",
    )
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cal.set_dates_range(today_start, None)
    return cal


KEYBOARDS = KeyboardFactory()
_REPO_FOR_KB: Repo | None = None
_SETTINGS: Settings | None = None


def _active_settings() -> Settings:
    if _SETTINGS is not None:
        return _SETTINGS
    return Settings(bot_token="", db_path="")


def main_keyboard(repo: Repo, tg_user_id: int) -> ReplyKeyboardMarkup:
    user = repo.get_user(tg_user_id)
    is_driver = user is not None and user["role"] == "driver"
    return KEYBOARDS.main_keyboard(is_driver=is_driver)


CHAT_UI: ChatUiService


def flow_keyboard():
    return KEYBOARDS.flow_keyboard()


def role_keyboard() -> InlineKeyboardMarkup:
    return KEYBOARDS.role_keyboard()


def role_switch_keyboard(current_role: str) -> InlineKeyboardMarkup:
    return KEYBOARDS.role_switch_keyboard(current_role)


def stops_keyboard(stops: list, prefix: str) -> InlineKeyboardMarkup:
    return KEYBOARDS.stops_keyboard(stops, prefix)


def localities_keyboard(prefix: str, localities: list[str]) -> InlineKeyboardMarkup:
    return KEYBOARDS.localities_keyboard(prefix, localities)


def districts_keyboard(prefix: str, districts: list[str]) -> InlineKeyboardMarkup:
    return KEYBOARDS.districts_keyboard(prefix, districts)


def add_back_button(markup: InlineKeyboardMarkup, back_callback: str) -> InlineKeyboardMarkup:
    return KEYBOARDS.add_back_button(markup, back_callback)


def time_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return KEYBOARDS.time_keyboard(prefix)


def seats_keyboard(prefix: str = "create_seats") -> InlineKeyboardMarkup:
    return KEYBOARDS.seats_keyboard(prefix)


def price_keyboard(prefix: str = "create_price") -> InlineKeyboardMarkup:
    return KEYBOARDS.price_keyboard(prefix)


def trips_keyboard(trips: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.trips_keyboard(trips)


def cancel_booking_keyboard(bookings: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.cancel_booking_keyboard(bookings)


def driver_manage_root_keyboard(open_trips: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.driver_manage_root_keyboard(open_trips)


def driver_trip_detail_keyboard(trip_id: int, bookings: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.driver_trip_detail_keyboard(trip_id, bookings)


def driver_rating_threshold_keyboard() -> InlineKeyboardMarkup:
    return KEYBOARDS.driver_rating_threshold_keyboard()


def favorite_routes_keyboard(rows: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.favorite_routes_keyboard(rows)


def add_favorite_keyboard(trip_id: int) -> InlineKeyboardMarkup:
    return KEYBOARDS.add_favorite_keyboard(trip_id)


def geo_suggested_start_stops_keyboard(ranked: list[tuple[sqlite3.Row, float]], mode: str) -> InlineKeyboardMarkup:
    return KEYBOARDS.geo_suggested_start_stops_keyboard(ranked, mode)


def account_kb_menu(show_become_driver: bool) -> InlineKeyboardMarkup:
    return KEYBOARDS.account_menu_keyboard(show_become_driver=show_become_driver)


def account_kb_back() -> InlineKeyboardMarkup:
    return KEYBOARDS.account_back_keyboard()


def _passenger_rating_hint(row) -> str:
    rc = int(row["rating_count"] or 0)
    ra = float(row["rating_avg"] or 0.0)
    if rc == 0:
        return "нет оценок"
    return f"{ra:.1f}, оценок: {rc}"


async def track_bot_message(message: Message) -> None:
    await CHAT_UI.track_bot_message(message)


async def send_clean_message(message: Message, text: str, **kwargs) -> Message:
    return await CHAT_UI.send_clean_message(message, text, **kwargs)


async def send_flow_step(message: Message, text: str, inline_markup: InlineKeyboardMarkup) -> None:
    await CHAT_UI.send_flow_step(message, text, inline_markup)


async def edit_or_send_clean(callback: CallbackQuery, text: str, **kwargs) -> None:
    await CHAT_UI.edit_or_send_clean(callback, text, **kwargs)


async def cleanup_chat(message: Message) -> int | None:
    return await CHAT_UI.cleanup_chat(message)


async def drop_empty_chat_bridge(message: Message, bridge_id: int | None) -> None:
    await CHAT_UI.drop_empty_chat_bridge(message, bridge_id)


# Сообщение с топом остановок по геолокации (редактируется при повторной отправке гео).
GEO_SUGGEST_MESSAGE_KEY = "geo_suggest_message_id"


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
    """Обновляет блок подсказок или отправляет новый; без полного cleanup_chat."""
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
        reply_markup=KEYBOARDS.location_reply_keyboard(),
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

FLOW_ORCHESTRATOR = TripFlowOrchestrator(
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

NAVIGATION_FLOW = NavigationFlow(
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

router.include_router(registration_router)
router.include_router(account_router)
router.include_router(favorites_router)
router.include_router(trip_search_router)
router.include_router(trip_create_router)
router.include_router(booking_router)
router.include_router(driver_manage_router)
router.include_router(rating_router)


async def _handle_start_locality_geo(
    message: Message,
    state: FSMContext,
    repo: Repo,
    *,
    mode: str,
) -> None:
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
    ranked = repo.nearest_stops_global(
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

    resolved = repo.nearest_locality_from_geo(lat, lng, max_km=st.locality_geo_max_km)
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


@router.callback_query(F.data.startswith("gxs:"))
async def geo_pick_suggested_start_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    cur = await state.get_state()
    if cur is None or not str(cur).endswith("start_locality"):
        await callback.answer("Шаг устарел. Начни выбор маршрута заново.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, mode, sid = parts
    if mode not in ("search", "create"):
        await callback.answer()
        return
    try:
        pid = int(sid)
    except ValueError:
        await callback.answer()
        return
    await FLOW_ORCHESTRATOR.transition_geo_pick_start_stop(callback, state, repo, mode, pid)


@router.callback_query(SimpleCalendarCallback.filter())
async def process_calendar_selection(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
    repo: Repo,
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

    if target == "search":
        if "start_point" not in data or "end_point" not in data:
            await state.clear()
            await edit_or_send_clean(
                callback, STALE_SEARCH_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id)
            )
            await callback.answer()
            return
        await state.update_data(trip_date=iso_date)
        trips = repo.find_open_trips(
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
        _, msg = repo.switch_role(callback.from_user.id, str(target_role), iso_date)
        await state.clear()
        await edit_or_send_clean(callback, msg, reply_markup=main_keyboard(repo, callback.from_user.id))
        await callback.answer()
        return

    await callback.answer("Сессия выбора даты не найдена. Начни заново.", show_alert=True)


@router.callback_query(F.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await NAVIGATION_FLOW.handle_callback_back(callback, state, repo)


@router.message(F.text == "⬅ Назад")
async def go_back_keyboard(message: Message, state: FSMContext, repo: Repo) -> None:
    await NAVIGATION_FLOW.handle_reply_back(message, state, repo)


@router.message()
async def fallback(message: Message, repo: Repo) -> None:
    await send_clean_message(
        message,
        "Используй кнопки меню или /start для регистрации.",
        reply_markup=main_keyboard(repo, message.from_user.id),
    )


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
    ids = repo.list_all_tg_user_ids()
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


async def run() -> None:
    global _REPO_FOR_KB, KEYBOARDS, _SETTINGS, CHAT_UI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s [%(filename)s:%(lineno)d] %(message)s",
    )
    container = build_container()
    _SETTINGS = container.settings
    KEYBOARDS = container.keyboards
    _REPO_FOR_KB = container.repo
    CHAT_UI = container.chat_ui
    settings = container.settings
    repo = container.repo

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    attach_to_dispatcher(dp, container, flow=FLOW_ORCHESTRATOR, navigation_flow=NAVIGATION_FLOW)
    dp.include_router(router)

    # Снимает webhook и не обрабатывает старые апдейты из очереди до рестарта.
    await bot.delete_webhook(drop_pending_updates=True)

    async def rating_prompt_loop() -> None:
        try:
            await asyncio.sleep(settings.rating_prompt_initial_delay_s)
            while True:
                try:
                    await process_pending_rating_prompts(bot, repo)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("rating_prompt_loop")
                try:
                    await asyncio.sleep(settings.rating_prompt_interval_s)
                except asyncio.CancelledError:
                    raise
        except asyncio.CancelledError:
            pass

    background_tasks: set[asyncio.Task[None]] = set()

    def _spawn(coro):
        task = asyncio.create_task(coro)
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return task

    _spawn(rating_prompt_loop())
    _spawn(push_main_menu_after_restart(bot, repo))

    try:
        await dp.start_polling(bot)
    finally:
        for t in list(background_tasks):
            t.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        await bot.session.close()
        container.db.close()
