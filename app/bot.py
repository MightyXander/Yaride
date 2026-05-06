from __future__ import annotations

import calendar
import logging
from datetime import date as date_cls
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram_calendar.schemas import SimpleCalAct

from app.chat_ui import ChatUiService
from app.config import load_settings
from app.db import Database
from app.formatting import format_trip_row, format_trip_when
from app.navigation_flow import NavigationFlow
from app.repo import Repo
from app.trip_flow import TripFlowOrchestrator
from app.ui import KeyboardFactory

logger = logging.getLogger(__name__)
router = Router()


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


KEYBOARDS = KeyboardFactory()
CHAT_UI = ChatUiService(
    main_keyboard_provider=KEYBOARDS.main_keyboard,
    flow_keyboard_provider=KEYBOARDS.flow_keyboard,
)


def main_keyboard():
    return KEYBOARDS.main_keyboard()


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


def debug_book_keyboard(trips: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.debug_book_keyboard(trips)


def cancel_booking_keyboard(bookings: list) -> InlineKeyboardMarkup:
    return KEYBOARDS.cancel_booking_keyboard(bookings)


async def track_bot_message(message: Message) -> None:
    await CHAT_UI.track_bot_message(message)


async def send_clean_message(message: Message, text: str, **kwargs) -> Message:
    return await CHAT_UI.send_clean_message(message, text, **kwargs)


async def send_flow_step(message: Message, text: str, inline_markup: InlineKeyboardMarkup) -> None:
    await CHAT_UI.send_flow_step(message, text, inline_markup)


async def edit_or_send_clean(callback: CallbackQuery, text: str, **kwargs) -> None:
    await CHAT_UI.edit_or_send_clean(callback, text, **kwargs)


async def cleanup_chat(message: Message) -> None:
    await CHAT_UI.cleanup_chat(message)


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
async def start(message: Message, state: FSMContext) -> None:
    await cleanup_chat(message)
    await state.clear()
    await state.set_state(Registration.waiting_name)
    sent = await message.answer(
        "Привет! Введи имя для профиля.\n"
        "После этого выбери роль: водитель или пассажир."
    )
    await track_bot_message(sent)


@router.message(Registration.waiting_name)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await send_clean_message(message, "Имя слишком короткое, попробуй ещё раз.")
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
    repo.upsert_user(callback.from_user.id, str(name), callback.from_user.username, role)
    await state.clear()
    await edit_or_send_clean(
        callback,
        "Профиль сохранён.\n"
        "Условия сервиса: плата покрывает бензин и износ, сервис не является такси.",
        reply_markup=main_keyboard(),
    )
    await callback.answer("Роль сохранена")


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
async def search_pick_end_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await FLOW_ORCHESTRATOR.pick_end_stop(callback, state, mode="search")


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

    trip = repo.find_open_trips()
    trip_item = next((item for item in trip if item["id"] == trip_id), None)
    await edit_or_send_clean(callback, f"Бронь #{booking_id} создана.", reply_markup=main_keyboard())
    if trip_item:
        driver_internal_id = trip_item["driver_id"]
        # Ищем tg id водителя через вспомогательный запрос.
        with repo.db.transaction() as conn:
            drow = conn.execute(
                "SELECT tg_user_id FROM users WHERE id = ?",
                (driver_internal_id,),
            ).fetchone()
        if drow:
            try:
                await callback.bot.send_message(
                    drow["tg_user_id"],
                    (
                        "Новая бронь на вашу поездку.\n"
                        f"Trip #{trip_id} | {trip_item['start_title']} -> {trip_item['end_title']} | "
                        f"{format_trip_when(trip_item['trip_date'], trip_item['departure_time'], trip_item['time_slot'])}"
                    ),
                )
            except Exception as err:
                logger.warning("Driver notify failed: %s", err)
    await callback.answer("Забронировано")


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
async def create_pick_end_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await FLOW_ORCHESTRATOR.pick_end_stop(callback, state, mode="create")


@router.callback_query(F.data.startswith("create_time:"))
async def create_set_time(callback: CallbackQuery, state: FSMContext) -> None:
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
async def create_set_seats(callback: CallbackQuery, state: FSMContext) -> None:
    seats = int(callback.data.split(":", 1)[1])
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
    price = int(callback.data.split(":", 1)[1])
    if price not in (100, 150, 200):
        await edit_or_send_clean(
            callback,
            "Доступные цены: 100, 150, 200.",
            reply_markup=add_back_button(price_keyboard(), "create_seats"),
        )
        await callback.answer()
        return
    data = await state.get_data()
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
        await edit_or_send_clean(callback, str(exc), reply_markup=main_keyboard())
        await state.clear()
        await callback.answer()
        return

    await state.clear()
    await edit_or_send_clean(callback, f"Поездка #{trip_id} создана и доступна для поиска.", reply_markup=main_keyboard())
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
    booking_id = int(data["booking_id"])
    try:
        _, payload = repo.cancel_booking_by_passenger(message.from_user.id, booking_id, reason)
    except ValueError as exc:
        await send_clean_message(message, str(exc))
        await state.clear()
        return
    await state.clear()
    await send_clean_message(message, f"Бронь #{booking_id} отменена.", reply_markup=main_keyboard())
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


@router.message(F.text == "Мои поездки")
async def my_trips(message: Message, repo: Repo) -> None:
    user = repo.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    trips = repo.list_driver_trips(message.from_user.id)
    if not trips:
        await send_clean_message(message, "У тебя пока нет созданных поездок.")
        return
    lines = ["Твои поездки:"]
    for t in trips:
        free = t["seats_total"] - t["seats_booked"]
        lines.append(
            f"#{t['id']} | {t['start_title']} -> {t['end_title']} | {format_trip_row(t)} | "
            f"{t['price_rub']} руб | свободно {free}/{t['seats_total']} | {t['status']}"
        )
    await send_clean_message(message, "\n".join(lines))


@router.message(F.text == "ВРЕМЕННО: Все поездки (debug)")
async def all_trips_debug(message: Message, repo: Repo) -> None:
    trips = repo.list_all_trips_for_debug()
    if not trips:
        await send_clean_message(message, "Пока нет ни одной созданной поездки.")
        return
    lines = ["[Временная debug-выдача] Все созданные поездки:"]
    for t in trips:
        free = t["seats_total"] - t["seats_booked"]
        lines.append(
            f"#{t['id']} | {t['driver_name']} | {t['start_title']} -> {t['end_title']} | "
            f"{format_trip_row(t)} | {t['price_rub']} руб | свободно {free}/{t['seats_total']} | {t['status']}"
        )
    open_trips = [t for t in trips if t["status"] == "open" and t["seats_booked"] < t["seats_total"]]
    if open_trips:
        await send_clean_message(
            message,
            "\n".join(lines) + "\n\nНиже кнопки быстрой debug-брони:",
            reply_markup=debug_book_keyboard(open_trips[:20]),
        )
    else:
        await send_clean_message(message, "\n".join(lines) + "\n\nНет открытых поездок для брони.")


@router.callback_query(F.data.startswith("debug_book:"))
async def debug_book_trip(callback: CallbackQuery, repo: Repo) -> None:
    trip_id = int(callback.data.split(":", 1)[1])
    user = repo.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start.", show_alert=True)
        return
    try:
        booking_id = repo.create_booking(callback.from_user.id, trip_id)
    except ValueError as exc:
        # Не редактируем сообщение с inline-кнопками, чтобы они не пропадали.
        await callback.answer(f"[DEBUG] Не удалось забронировать: {exc}", show_alert=True)
        return
    await callback.answer(f"[DEBUG] Бронь #{booking_id} создана для поездки #{trip_id}.", show_alert=True)


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
        await state.update_data(trip_date=iso_date)
        trips = repo.find_open_trips(
            start_point_id=data.get("start_point"),
            end_point_id=data.get("end_point"),
            trip_date=iso_date,
        )
        await state.clear()
        if not trips:
            await edit_or_send_clean(callback, "Подходящих поездок пока нет.", reply_markup=main_keyboard())
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
        await edit_or_send_clean(callback, msg, reply_markup=main_keyboard())
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
async def fallback(message: Message) -> None:
    await send_clean_message(message, "Используй кнопки меню или /start для регистрации.", reply_markup=main_keyboard())


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    db = Database(settings.db_path)
    db.init_schema()
    repo = Repo(db)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp["repo"] = repo
    dp.include_router(router)

    await dp.start_polling(bot)
