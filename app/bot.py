from __future__ import annotations

import asyncio
import calendar
import html
import logging
import os
import sqlite3
from datetime import date as date_cls
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram_calendar.schemas import SimpleCalAct

from app.chat_ui import ChatUiService
from app.filters import RatingReviewReplyFilter
from app.config import load_settings
from app.db import Database
from app.driver_license import normalize_dl_series_number, parse_expiry_date, validate_license_not_expired
from app.formatting import format_trip_row, format_trip_when
from app.navigation_flow import NavigationFlow
from app.rating_worker import process_pending_rating_prompts
from app.repo import Repo
from app.security.rating_input import MAX_REVIEW_CHARS, parse_rate_callback_data
from app.services.rating_service import RatingService
from app.trip_flow import (
    GEO_USER_LOCATION_IDS_KEY,
    TripFlowOrchestrator,
    delete_tracked_user_geo_messages,
)
from app.ui import KeyboardFactory

logger = logging.getLogger(__name__)
router = Router()

# Устаревшие inline-кнопки при пустом FSM
STALE_CREATE_FLOW = (
    "Сессия создания поездки устарела (часто это старая кнопка). "
    "Начни заново: «Создать поездку»."
)
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
                        callback_data=SimpleCalendarCallback(act=SimpleCalAct.day, year=year, month=month, day=day).pack(),
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


class Registration(StatesGroup):
    waiting_name = State()
    waiting_role = State()
    waiting_dl_series = State()
    waiting_dl_expiry = State()
    waiting_role_switch_date = State()


class TripCreate(StatesGroup):
    start_locality = State()
    start_district = State()
    start_admin_area = State()
    start_stop = State()
    end_locality = State()
    end_district = State()
    end_admin_area = State()
    end_stop = State()
    trip_date = State()
    departure_time = State()
    seats = State()
    price = State()


class TripSearch(StatesGroup):
    start_locality = State()
    start_district = State()
    start_admin_area = State()
    start_stop = State()
    end_locality = State()
    end_district = State()
    end_admin_area = State()
    end_stop = State()
    trip_date = State()


class CancelBooking(StatesGroup):
    waiting_reason = State()


class AccountUpgrade(StatesGroup):
    """Пассажир → водитель из раздела «Аккаунт» (те же проверки ВУ, что при регистрации)."""

    waiting_dl_series = State()
    waiting_dl_expiry = State()


KEYBOARDS = KeyboardFactory()
_REPO_FOR_KB: Repo | None = None


def main_keyboard(repo: Repo, tg_user_id: int) -> ReplyKeyboardMarkup:
    user = repo.get_user(tg_user_id)
    is_driver = user is not None and user["role"] == "driver"
    return KEYBOARDS.main_keyboard(is_driver=is_driver)


def _chat_main_kb(tg_user_id: int) -> ReplyKeyboardMarkup:
    if _REPO_FOR_KB is None:
        return KEYBOARDS.main_keyboard(is_driver=False)
    return main_keyboard(_REPO_FOR_KB, tg_user_id)


CHAT_UI = ChatUiService(
    main_keyboard_provider=_chat_main_kb,
    flow_keyboard_provider=KEYBOARDS.flow_keyboard,
)


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


def geo_suggested_start_stops_keyboard(
    ranked: list[tuple[sqlite3.Row, float]], mode: str
) -> InlineKeyboardMarkup:
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


LOCALITY_GEO_MAX_KM = 150.0
GEO_SUGGEST_LIMIT = 5
GEO_SUGGEST_MAX_KM = 85.0

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


@router.message(Command("start"))
async def start(message: Message, state: FSMContext, repo: Repo) -> None:
    bridge_id = await cleanup_chat(message)
    await state.clear()
    user = repo.get_user(message.from_user.id)
    if user:
        name = str(user["name"] or "").strip() or (message.from_user.first_name or "друг")
        await state.update_data(name=name)
        await state.set_state(Registration.waiting_role)
        text = f"<b>{html.escape(name)}</b> Давно не виделись. Выберите вашу роль:"
        sent = await message.answer(text, parse_mode="HTML", reply_markup=role_keyboard())
        await track_bot_message(sent)
        await drop_empty_chat_bridge(message, bridge_id)
        return
    await state.set_state(Registration.waiting_name)
    sent = await message.answer("Привет! Введи имя пользователя — так тебя будут видеть другие участники.")
    await track_bot_message(sent)
    await drop_empty_chat_bridge(message, bridge_id)


@router.message(Registration.waiting_name)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await send_clean_message(message, "Имя пользователя слишком короткое, попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.waiting_role)
    await send_clean_message(message, "Выбери роль:", reply_markup=role_keyboard())


@router.callback_query(F.data.startswith("set_role:"))
async def reg_role(callback, state: FSMContext, repo: Repo) -> None:
    role = callback.data.split(":", 1)[1]
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await edit_or_send_clean(callback, "Сессия регистрации устарела. Нажми /start.")
        await state.clear()
        await callback.answer()
        return
    if role == "passenger":
        repo.upsert_user(callback.from_user.id, str(name), callback.from_user.username, "passenger")
        await state.clear()
        await edit_or_send_clean(
            callback,
            "Профиль сохранён.\n"
            "Условия сервиса: плата покрывает бензин и износ, сервис не является такси.",
            reply_markup=main_keyboard(repo, callback.from_user.id),
        )
        await callback.answer("Роль сохранена")
        return
    if role == "driver":
        await state.set_state(Registration.waiting_dl_series)
        await edit_or_send_clean(
            callback,
            "Роль «водитель»: сначала локальная проверка формата ВУ (без запросов в ГИБДД).\n\n"
            "Введи серию и номер как на пластиковом бланке: 4 цифры, 2 буквы "
            "(А, В, Е, К, М, Н, О, Р, С, Т, У, Х), 6 цифр. Можно с пробелами — например 9916 АВ 123456.",
            reply_markup=flow_keyboard(),
        )
        await callback.answer()
        return
    await callback.answer("Неизвестная роль.", show_alert=True)


@router.message(Registration.waiting_dl_series)
async def reg_dl_series(message: Message, state: FSMContext) -> None:
    ok, normalized, err = normalize_dl_series_number(message.text or "")
    if not ok:
        await send_clean_message(message, err or "Некорректные данные ВУ.")
        return
    await state.update_data(dl_series_number=normalized)
    await state.set_state(Registration.waiting_dl_expiry)
    await send_clean_message(
        message,
        "Теперь введи дату окончания срока действия ВУ (поле «3b») в формате ДД.ММ.ГГГГ.",
        reply_markup=flow_keyboard(),
    )


@router.message(Registration.waiting_dl_expiry)
async def reg_dl_expiry(message: Message, state: FSMContext, repo: Repo) -> None:
    ok, expiry_date, err = parse_expiry_date(message.text or "")
    if not ok or not expiry_date:
        await send_clean_message(message, err or "Некорректная дата.")
        return
    ok_exp, msg_exp = validate_license_not_expired(expiry_date)
    if not ok_exp:
        await send_clean_message(message, msg_exp or "ВУ недействительно.")
        return
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await send_clean_message(message, "Сессия регистрации устарела. Нажми /start.")
        await state.clear()
        return
    dl_series = data.get("dl_series_number")
    if not dl_series:
        await send_clean_message(message, "Сначала введи серию и номер ВУ.")
        await state.set_state(Registration.waiting_dl_series)
        return
    try:
        repo.upsert_user(
            message.from_user.id,
            str(name),
            message.from_user.username,
            "driver",
            dl_series_number=str(dl_series),
            dl_valid_until=expiry_date.isoformat(),
        )
    except ValueError as exc:
        await send_clean_message(message, str(exc))
        return
    await state.clear()
    await send_clean_message(
        message,
        "Профиль водителя сохранён: формат ВУ проверен локально.\n"
        "Условия сервиса: плата покрывает бензин и износ, сервис не является такси.",
        reply_markup=main_keyboard(repo, message.from_user.id),
    )


@router.message(F.text == "Избранные маршруты")
async def favorite_routes_menu(message: Message, repo: Repo) -> None:
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    rows = repo.list_favorite_routes(message.from_user.id)
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


@router.message(F.text == "Аккаунт")
async def account_open(message: Message, repo: Repo) -> None:
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    await send_clean_message(
        message,
        "Раздел «Аккаунт»:",
        reply_markup=account_kb_menu(show_become_driver=user["role"] == "passenger"),
    )


@router.callback_query(F.data.startswith("account:"))
async def account_panel(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    action = callback.data.split(":", 1)[1]
    user = repo.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start.", show_alert=True)
        return

    show_drv = user["role"] == "passenger"
    menu = account_kb_menu(show_become_driver=show_drv)
    back = account_kb_back()

    if action == "root":
        await edit_or_send_clean(callback, "Раздел «Аккаунт»:", reply_markup=menu)
        await callback.answer()
        return

    if action == "main_menu":
        if callback.message:
            await send_clean_message(
                callback.message,
                "Главное меню",
                reply_markup=main_keyboard(repo, callback.from_user.id),
            )
        await callback.answer()
        return

    if action == "rating":
        rc = int(user["rating_count"] or 0)
        ra = float(user["rating_avg"] or 0.0)
        text = (
            f"Средний рейтинг: {ra:.1f}\nВсего оценок: {rc}" if rc > 0 else "Пока нет оценок от других пользователей."
        )
        await edit_or_send_clean(callback, text, reply_markup=back)
        await callback.answer()
        return

    if action == "reviews":
        rows = repo.list_ratings_received(callback.from_user.id)
        if not rows:
            txt = "Пока никто не оставил оценок после поездок."
        else:
            lines = []
            for r in rows[:25]:
                line = (
                    f"★ {int(r['stars'])} — от {html.escape(str(r['rater_name']))} | поездка #{r['trip_id']} | "
                    f"{r['trip_date']} {r['departure_time']}"
                )
                rt = r["review_text"]
                if rt:
                    line += f"\n   «{html.escape(str(rt))}»"
                lines.append(line)
            txt = "Оценки после поездок:\n" + "\n".join(lines)
            if len(rows) > 25:
                txt += "\n…"
        await edit_or_send_clean(callback, txt, reply_markup=back)
        await callback.answer()
        return

    if action == "name":
        un = user["username"]
        if un:
            txt = f"Имя в сервисе: {user['name']}\nUsername в Telegram: @{un}"
        else:
            txt = f"Имя в сервисе: {user['name']}\nUsername в Telegram: не указан в профиле Telegram."
        await edit_or_send_clean(callback, txt, reply_markup=back)
        await callback.answer()
        return

    if action == "upgrade_driver":
        if user["role"] != "passenger":
            await callback.answer("Ты уже водитель.", show_alert=True)
            return
        await state.set_state(AccountUpgrade.waiting_dl_series)
        await edit_or_send_clean(
            callback,
            "Стать водителем: проверка формата ВУ (без запросов в ГИБДД).\n\n"
            "Введи серию и номер как на пластиковом бланке: 4 цифры, 2 буквы "
            "(А, В, Е, К, М, Н, О, Р, С, Т, У, Х), 6 цифр. Можно с пробелами — например 9916 АВ 123456.",
            reply_markup=flow_keyboard(),
        )
        await callback.answer()
        return

    await callback.answer()


@router.message(AccountUpgrade.waiting_dl_series)
async def account_upgrade_dl_series(message: Message, state: FSMContext) -> None:
    ok, normalized, err = normalize_dl_series_number(message.text or "")
    if not ok:
        await send_clean_message(message, err or "Некорректные данные ВУ.")
        return
    await state.update_data(dl_series_number=normalized)
    await state.set_state(AccountUpgrade.waiting_dl_expiry)
    await send_clean_message(
        message,
        "Введи дату окончания срока действия ВУ (поле «3b») в формате ДД.ММ.ГГГГ.",
        reply_markup=flow_keyboard(),
    )


@router.message(AccountUpgrade.waiting_dl_expiry)
async def account_upgrade_dl_expiry(message: Message, state: FSMContext, repo: Repo) -> None:
    ok, expiry_date, err = parse_expiry_date(message.text or "")
    if not ok or not expiry_date:
        await send_clean_message(message, err or "Некорректная дата.")
        return
    ok_exp, msg_exp = validate_license_not_expired(expiry_date)
    if not ok_exp:
        await send_clean_message(message, msg_exp or "ВУ недействительно.")
        return
    user = repo.get_user(message.from_user.id)
    if not user or user["role"] != "passenger":
        await send_clean_message(message, "Сессия устарела или роль уже изменена.")
        await state.clear()
        return
    data = await state.get_data()
    dl_series = data.get("dl_series_number")
    if not dl_series:
        await send_clean_message(message, "Сначала введи серию и номер ВУ.")
        await state.set_state(AccountUpgrade.waiting_dl_series)
        return
    try:
        repo.upsert_user(
            message.from_user.id,
            str(user["name"]),
            message.from_user.username,
            "driver",
            dl_series_number=str(dl_series),
            dl_valid_until=expiry_date.isoformat(),
        )
    except ValueError as exc:
        await send_clean_message(message, str(exc))
        return
    await state.clear()
    await send_clean_message(
        message,
        "Ты зарегистрирован как водитель. Формат ВУ проверен локально.\n"
        "В меню доступны создание поездок и раздел «Управление».",
        reply_markup=main_keyboard(repo, message.from_user.id),
    )


@router.message(F.text.in_(["Найти поездки"]))
async def find_trips_start(message: Message, state: FSMContext, repo: Repo) -> None:
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    await FLOW_ORCHESTRATOR.begin(message, state, repo, mode="search")


@router.callback_query(F.data.startswith("Sfl:"))
async def search_pick_start_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfd:"))
async def search_pick_start_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfa:"))
async def search_pick_start_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="search", is_start=True)


@router.callback_query(F.data.startswith("Sfp:"))
async def search_pick_start_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_start_stop(callback, state, repo, mode="search")


@router.callback_query(F.data.startswith("Stl:"))
async def search_pick_end_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Std:"))
async def search_pick_end_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Sta:"))
async def search_pick_end_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="search", is_start=False)


@router.callback_query(F.data.startswith("Stp:"))
async def search_pick_end_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_end_stop(callback, state, repo, mode="search")


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

    ranked = repo.nearest_stops_global(
        lat,
        lng,
        limit=GEO_SUGGEST_LIMIT,
        max_km=GEO_SUGGEST_MAX_KM,
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

    resolved = repo.nearest_locality_from_geo(lat, lng, max_km=LOCALITY_GEO_MAX_KM)
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


@router.message(StateFilter(TripSearch.start_locality), F.location)
async def search_start_locality_geo(message: Message, state: FSMContext, repo: Repo) -> None:
    await _handle_start_locality_geo(message, state, repo, mode="search")


@router.message(StateFilter(TripCreate.start_locality), F.location)
async def create_start_locality_geo(message: Message, state: FSMContext, repo: Repo) -> None:
    await _handle_start_locality_geo(message, state, repo, mode="create")


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


@router.callback_query(F.data.startswith("book:"))
async def book_trip(callback, repo: Repo) -> None:
    trip_id = int(callback.data.split(":")[1])
    user = repo.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start.", show_alert=True)
        return
    if user["role"] != "passenger":
        await callback.answer("Бронировать поездки может только пассажир.", show_alert=True)
        return
    try:
        booking_id = repo.create_booking(callback.from_user.id, trip_id)
    except ValueError as exc:
        # Не перерисовываем сообщение при ошибке, чтобы inline-кнопки не пропадали.
        await callback.answer(str(exc), show_alert=True)
        return

    trip_item = repo.get_trip_public_card(trip_id)
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


@router.callback_query(F.data.startswith("fav_add:"))
async def fav_add(callback: CallbackQuery, repo: Repo) -> None:
    if not repo.get_user(callback.from_user.id):
        await callback.answer("Сначала /start.", show_alert=True)
        return
    tid = int(callback.data.split(":")[1])
    try:
        added = repo.add_favorite_from_trip(callback.from_user.id, tid)
    except ValueError:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    await callback.answer("Маршрут добавлен в избранное" if added else "Этот маршрут уже в избранном")


@router.callback_query(F.data.startswith("fav_route:"))
async def favorite_route_pick_date(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    fid = int(callback.data.split(":")[1])
    row = repo.get_favorite_route_owned(callback.from_user.id, fid)
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


@router.callback_query(F.data.startswith("rate:"))
async def submit_trip_rating_callback(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    parsed = parse_rate_callback_data(callback.data or "")
    if not parsed:
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    trip_id, rated_tg, stars = parsed
    if callback.message is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    prompt = await callback.message.answer(
        f"Оценка {stars}★.\nОтветь на это сообщение: короткий комментарий (до {MAX_REVIEW_CHARS} символов) "
        "или отправь «-» без текста.",
        reply_markup=ForceReply(input_field_placeholder="Комментарий или -"),
    )
    await state.update_data(rating_review_collect=(trip_id, rated_tg, stars, prompt.message_id))
    await callback.answer()


@router.message(F.text == "Создать поездку")
async def create_trip_start(message: Message, state: FSMContext, repo: Repo) -> None:
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    if user["role"] != "driver":
        await send_clean_message(message, "Создавать поездки может только водитель.")
        return
    await FLOW_ORCHESTRATOR.begin(message, state, repo, mode="create")


@router.callback_query(F.data.startswith("Cfl:"))
async def create_pick_start_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfd:"))
async def create_pick_start_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfa:"))
async def create_pick_start_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="create", is_start=True)


@router.callback_query(F.data.startswith("Cfp:"))
async def create_pick_start_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_start_stop(callback, state, repo, mode="create")


@router.callback_query(F.data.startswith("Ctl:"))
async def create_pick_end_locality(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_locality(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Ctd:"))
async def create_pick_end_district(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_district(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Cta:"))
async def create_pick_end_admin(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_admin(callback, state, repo, mode="create", is_start=False)


@router.callback_query(F.data.startswith("Ctp:"))
async def create_pick_end_stop(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await FLOW_ORCHESTRATOR.pick_end_stop(callback, state, repo, mode="create")


@router.callback_query(F.data.startswith("create_time:"))
async def create_set_time(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    data = await state.get_data()
    if "trip_date" not in data:
        await edit_or_send_clean(callback, STALE_CREATE_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id))
        await state.clear()
        await callback.answer()
        return
    departure_time = callback.data.split(":", 1)[1]
    await state.update_data(departure_time=departure_time)
    await state.set_state(TripCreate.seats)
    await edit_or_send_clean(
        callback,
        "Выбери количество пассажиров:",
        reply_markup=add_back_button(seats_keyboard(), "create_time"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("create_seats:"))
async def create_set_seats(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    data = await state.get_data()
    if "trip_date" not in data or "departure_time" not in data:
        await edit_or_send_clean(callback, STALE_CREATE_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id))
        await state.clear()
        await callback.answer()
        return
    try:
        seats = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    if seats < 2 or seats > 4:
        await edit_or_send_clean(
            callback,
            "Допустимо только 2-4 пассажира.",
            reply_markup=add_back_button(seats_keyboard(), "create_time"),
        )
        await callback.answer()
        return
    await state.update_data(seats=seats)
    await state.set_state(TripCreate.price)
    await edit_or_send_clean(callback, "Выбери цену поездки:", reply_markup=add_back_button(price_keyboard(), "create_seats"))
    await callback.answer()


@router.callback_query(F.data.startswith("create_price:"))
async def create_set_price(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    try:
        price = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return
    if price not in (100, 150, 200):
        await edit_or_send_clean(
            callback,
            "Доступные цены: 100, 150, 200.",
            reply_markup=add_back_button(price_keyboard(), "create_seats"),
        )
        await callback.answer()
        return
    data = await state.get_data()
    required_keys = ("start_point", "end_point", "trip_date", "departure_time", "seats")
    if any(k not in data or data[k] is None for k in required_keys):
        await edit_or_send_clean(callback, STALE_CREATE_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id))
        await state.clear()
        await callback.answer()
        return
    try:
        trip_id = repo.create_trip(
            tg_driver_id=callback.from_user.id,
            start_point_id=data["start_point"],
            end_point_id=data["end_point"],
            trip_date=data["trip_date"],
            departure_time=data["departure_time"],
            seats_total=data["seats"],
            price_rub=price,
        )
    except ValueError as exc:
        await edit_or_send_clean(callback, str(exc), reply_markup=main_keyboard(repo, callback.from_user.id))
        await state.clear()
        await callback.answer()
        return

    await state.clear()
    await edit_or_send_clean(
        callback,
        f"Поездка #{trip_id} создана и доступна для поиска.",
        reply_markup=main_keyboard(repo, callback.from_user.id),
    )
    await callback.answer()


@router.message(F.text == "Мои брони")
async def my_bookings(message: Message, repo: Repo) -> None:
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    bookings = repo.list_passenger_bookings(message.from_user.id)
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
async def cancel_booking_start(callback, state: FSMContext, repo: Repo) -> None:
    booking_id = int(callback.data.split(":")[1])
    booking = repo.get_booking_for_cancel(callback.from_user.id, booking_id)
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
        _, payload = repo.cancel_booking_by_passenger(message.from_user.id, booking_id, reason)
    except ValueError as exc:
        await send_clean_message(message, str(exc))
        await state.clear()
        return
    await state.clear()
    await send_clean_message(message, f"Бронь #{booking_id} отменена.", reply_markup=main_keyboard(repo, message.from_user.id))
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


@router.message(F.text == "История поездок")
async def my_trips(message: Message, repo: Repo) -> None:
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
        await callback.answer(str(exc), show_alert=True)
        return
    await edit_or_send_clean(callback, "Бронь отклонена, место снова доступно.", reply_markup=main_keyboard(repo, callback.from_user.id))
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
        await callback.answer(str(exc), show_alert=True)
        return
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
            await edit_or_send_clean(callback, STALE_SEARCH_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id))
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
            await edit_or_send_clean(callback, "Подходящих поездок пока нет.", reply_markup=main_keyboard(repo, callback.from_user.id))
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
            await edit_or_send_clean(callback, STALE_CREATE_FLOW, reply_markup=main_keyboard(repo, callback.from_user.id))
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


@router.message(F.text == "⬅ Назад", StateFilter(AccountUpgrade.waiting_dl_expiry))
async def account_upgrade_back_from_expiry(message: Message, state: FSMContext) -> None:
    await state.set_state(AccountUpgrade.waiting_dl_series)
    await send_clean_message(
        message,
        "Введи серию и номер ВУ как на пластиковом бланке.",
        reply_markup=flow_keyboard(),
    )


@router.message(F.text == "⬅ Назад", StateFilter(AccountUpgrade.waiting_dl_series))
async def account_upgrade_back_from_series(message: Message, state: FSMContext, repo: Repo) -> None:
    await state.clear()
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    await send_clean_message(
        message,
        "Раздел «Аккаунт»:",
        reply_markup=account_kb_menu(show_become_driver=user["role"] == "passenger"),
    )


@router.message(F.text == "⬅ Назад")
async def go_back_keyboard(message: Message, state: FSMContext, repo: Repo) -> None:
    await NAVIGATION_FLOW.handle_reply_back(message, state, repo)


@router.message(RatingReviewReplyFilter())
async def complete_trip_rating_review(
    message: Message,
    state: FSMContext,
    repo: Repo,
    rating_completion: tuple[int, int, int],
) -> None:
    trip_id, rated_tg, stars = rating_completion
    svc = RatingService(repo)
    try:
        svc.submit(message.from_user.id, trip_id, rated_tg, stars, message.text)
    except ValueError as exc:
        await state.update_data(rating_review_collect=None)
        await message.answer(str(exc))
        return
    await state.update_data(rating_review_collect=None)
    await message.answer("Спасибо, оценка сохранена.")


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
    global _REPO_FOR_KB
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    db = Database(settings.db_path)
    db.init_schema()
    repo = Repo(db)
    _REPO_FOR_KB = repo
    CHAT_UI.attach_database(db)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp["repo"] = repo
    dp.include_router(router)

    # Снимает webhook и не обрабатывает старые апдейты из очереди до рестарта.
    await bot.delete_webhook(drop_pending_updates=True)

    async def rating_prompt_loop() -> None:
        await asyncio.sleep(45)
        while True:
            try:
                await process_pending_rating_prompts(bot, repo)
            except Exception:
                logger.exception("rating_prompt_loop")
            await asyncio.sleep(180)

    asyncio.create_task(rating_prompt_loop())
    asyncio.create_task(push_main_menu_after_restart(bot, repo))

    await dp.start_polling(bot)
