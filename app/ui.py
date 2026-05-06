from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class KeyboardFactory:
    """Factory for all bot keyboards."""

    def __init__(self, time_step_minutes: int = 30) -> None:
        self._time_choices = self._build_time_choices(time_step_minutes)

    @staticmethod
    def _build_time_choices(step_minutes: int) -> list[str]:
        out: list[str] = []
        for hour in range(6, 23):
            for minute in range(0, 60, step_minutes):
                out.append(f"{hour:02d}:{minute:02d}")
        return out

    def main_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Найти поездки"), KeyboardButton(text="Создать поездку"), KeyboardButton(text="Мои брони")],
                [KeyboardButton(text="Мои поездки"), KeyboardButton(text="ВРЕМЕННО: Все поездки (debug)")],
            ],
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
    def add_back_button(markup: InlineKeyboardMarkup, back_callback: str) -> InlineKeyboardMarkup:
        # Inline-кнопки "Назад" отключены: навигация только через reply-кнопку.
        _ = back_callback
        return markup

    def time_keyboard(self, prefix: str) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for time_value in self._time_choices:
            kb.button(text=time_value, callback_data=f"{prefix}:{time_value}")
        kb.adjust(4)
        return kb.as_markup()

    @staticmethod
    def seats_keyboard(prefix: str = "create_seats") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for seats in [2, 3, 4]:
            kb.button(text=str(seats), callback_data=f"{prefix}:{seats}")
        kb.adjust(3)
        return kb.as_markup()

    @staticmethod
    def price_keyboard(prefix: str = "create_price") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for price in [100, 150, 200]:
            kb.button(text=f"{price} руб", callback_data=f"{prefix}:{price}")
        kb.adjust(3)
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

    @staticmethod
    def debug_book_keyboard(trips: list) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for trip in trips:
            free = trip["seats_total"] - trip["seats_booked"]
            kb.button(
                text=f"[DEBUG] Бронь #{trip['id']} ({free} мест)",
                callback_data=f"debug_book:{trip['id']}",
            )
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def cancel_booking_keyboard(bookings: list) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for booking in bookings:
            if booking["status"] == "active":
                kb.button(
                    text=f"Отменить бронь #{booking['id']} (trip #{booking['trip_id']})",
                    callback_data=f"cancel_booking:{booking['id']}",
                )
        kb.adjust(1)
        return kb.as_markup()
