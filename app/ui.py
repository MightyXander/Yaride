"""Фабрика всех клавиатур бота — единственное место, где собираются InlineKeyboardMarkup и ReplyKeyboardMarkup.

Централизация гарантирует согласованность callback_data-префиксов и порядка кнопок во всех хендлерах.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings


class KeyboardFactory:
    """Единственный источник истины для клавиатур: хендлеры вызывают методы фабрики, не строят markup вручную."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        time_step_minutes: int | None = None,
    ) -> None:
        if settings is None:
            settings = Settings(bot_token="", db_path="")
        if time_step_minutes is not None:
            settings.time_step_minutes = time_step_minutes
        self._settings = settings
        self._time_choices = self._build_time_choices(
            settings.time_step_minutes,
            settings.work_hours_start,
            settings.work_hours_end,
        )

    @staticmethod
    def _build_time_choices(step_minutes: int, hour_start: int, hour_end: int) -> list[str]:
        """Предварительно строим список времён при инициализации — он одинаков для всех вызовов time_keyboard."""
        out: list[str] = []
        for hour in range(hour_start, hour_end):
            for minute in range(0, 60, step_minutes):
                out.append(f"{hour:02d}:{minute:02d}")
        return out

    def main_keyboard(self, *, is_driver: bool = False) -> ReplyKeyboardMarkup:
        if is_driver:
            row1 = [
                KeyboardButton(text="Найти поездки"),
                KeyboardButton(text="Создать поездку"),
                KeyboardButton(text="Мои брони"),
            ]
            row2 = [KeyboardButton(text="История поездок"), KeyboardButton(text="Управление")]
        else:
            row1 = [KeyboardButton(text="Найти поездки"), KeyboardButton(text="Мои брони")]
            row2 = [KeyboardButton(text="История поездок")]
        row3 = [KeyboardButton(text="Избранные маршруты")]
        row4 = [KeyboardButton(text="Аккаунт")]
        return ReplyKeyboardMarkup(
            keyboard=[row1, row2, row3, row4],
            resize_keyboard=True,
            one_time_keyboard=False,
            is_persistent=True,
        )

    def flow_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅ Назад")]],
            resize_keyboard=True,
            one_time_keyboard=False,
            is_persistent=True,
        )

    @staticmethod
    def location_reply_keyboard() -> ReplyKeyboardMarkup:
        """Reply-клавиатура: отправить геолокацию или вернуться (навигация «Назад» как в других шагах)."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📍 Отправить местоположение", request_location=True)],
                [KeyboardButton(text="⬅ Назад")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            is_persistent=True,
        )

    @staticmethod
    def role_keyboard() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.button(text="Водитель", callback_data="set_role:driver")
        kb.button(text="Пассажир", callback_data="set_role:passenger")
        kb.adjust(2)
        return kb.as_markup()

    @staticmethod
    def role_switch_keyboard(current_role: str) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        target = "passenger" if current_role == "driver" else "driver"
        title = "Стать пассажиром" if target == "passenger" else "Стать водителем"
        kb.button(text=title, callback_data=f"switch_role_target:{target}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def stops_keyboard(stops: list, prefix: str) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for point in stops:
            kb.button(text=point["title"], callback_data=f"{prefix}:{point['id']}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def localities_keyboard(prefix: str, localities: list[str]) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for i, loc in enumerate(localities):
            kb.button(text=loc, callback_data=f"{prefix}:{i}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def districts_keyboard(prefix: str, districts: list[str]) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for i, district in enumerate(districts):
            label = district if district else "Весь населённый пункт"
            kb.button(text=label, callback_data=f"{prefix}:{i}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def with_back_button(markup: InlineKeyboardMarkup, target: str = "menu") -> InlineKeyboardMarkup:
        """Добавляет в конец клавиатуры inline-кнопку «⬅ Назад» с `callback_data=f"back:{target}"`.

        Используется в root-меню (Управление / Мои брони / Избранные / Аккаунт), чтобы дать
        одним кликом уйти обратно. `target` обрабатывается в `NavigationFlow.handle_callback_back`
        (для `menu` — clear + Главное меню; кастомные таргеты — где-то ниже по стеку handler'ов).
        Сама исходная клавиатура не модифицируется — возвращается новый markup.
        """
        rows = [list(row) for row in markup.inline_keyboard]
        rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data=f"back:{target}")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def time_keyboard(self, prefix: str) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for time_value in self._time_choices:
            kb.button(text=time_value, callback_data=f"{prefix}:{time_value}")
        kb.adjust(4)
        return kb.as_markup()

    def seats_keyboard(self, prefix: str = "create_seats") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for seats in self._settings.seats_choices:
            kb.button(text=str(seats), callback_data=f"{prefix}:{seats}")
        kb.adjust(len(self._settings.seats_choices) or 3)
        return kb.as_markup()

    def price_keyboard(self, prefix: str = "create_price") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for price in self._settings.price_choices:
            kb.button(text=f"{price} руб", callback_data=f"{prefix}:{price}")
        kb.adjust(len(self._settings.price_choices) or 3)
        return kb.as_markup()

    @staticmethod
    def trips_keyboard(trips: list) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for trip in trips:
            free = trip["seats_total"] - trip["seats_booked"]
            kb.button(
                text=f"#{trip['id']} {trip['start_title']} -> {trip['end_title']} ({free} мест)",
                callback_data=f"book:{trip['id']}",
            )
        kb.adjust(1)
        return kb.as_markup()

    def webapp_button_keyboard(self, url: str | None = None) -> InlineKeyboardMarkup:
        """Кнопка «Открыть приложение» с WebAppInfo (переход в Mini App)."""
        webapp_url = url or self._settings.miniapp_url
        if not webapp_url:
            return InlineKeyboardMarkup(inline_keyboard=[])
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=webapp_url))]]
        )

    @staticmethod
    def back_to_menu_keyboard() -> InlineKeyboardMarkup:
        """Одиночная inline-кнопка «⬅ В главное меню» для экранов без собственных действий."""
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅ В главное меню", callback_data="back:menu")
        kb.adjust(1)
        return kb.as_markup()
