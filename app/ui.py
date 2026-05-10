from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings


class KeyboardFactory:
    """Factory for all bot keyboards."""

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

    @staticmethod
    def driver_manage_root_keyboard(open_trips: list) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for t in open_trips:
            free = int(t["seats_total"]) - int(t["seats_booked"])
            st = str(t["start_title"]).replace("\n", " ")[:14]
            en = str(t["end_title"]).replace("\n", " ")[:14]
            kb.button(
                text=f"#{t['id']} {st}→{en} ({free})",
                callback_data=f"manage_trip:{t['id']}",
            )
        kb.button(text="Порог рейтинга пассажиров", callback_data="thr_menu")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def driver_trip_detail_keyboard(trip_id: int, bookings: list) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for b in bookings:
            bid = int(b["booking_id"])
            name = str(b["passenger_name"]).replace("\n", " ")[:16]
            kb.button(text=f"Отклонить: {name}", callback_data=f"reject_bk:{bid}")
        kb.button(text="Отменить поездку полностью", callback_data=f"cancel_trip:{trip_id}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def driver_rating_threshold_keyboard() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.button(text="Не ниже 3.0", callback_data="thr_set:3.0")
        kb.button(text="Не ниже 4.0", callback_data="thr_set:4.0")
        kb.button(text="Не ниже 4.5", callback_data="thr_set:4.5")
        kb.button(text="Выключить фильтр", callback_data="thr_set:off")
        kb.adjust(2)
        return kb.as_markup()

    @staticmethod
    def favorite_routes_keyboard(rows: list) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for r in rows:
            st = str(r["start_title"]).replace("\n", " ")
            en = str(r["end_title"]).replace("\n", " ")
            label = f"{st} → {en}"
            if len(label) > 60:
                label = label[:57] + "…"
            kb.button(text=label, callback_data=f"fav_route:{int(r['id'])}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def add_favorite_keyboard(trip_id: int) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.button(text="Добавить маршрут в избранное", callback_data=f"fav_add:{trip_id}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def geo_suggested_start_stops_keyboard(
        ranked: list[tuple[object, float]],
        mode: str,
    ) -> InlineKeyboardMarkup:
        """Подсказки посадки по геолокации: callback gxs:{mode}:{point_id}."""
        kb = InlineKeyboardBuilder()
        for row, dkm in ranked:
            rid = int(row["id"])
            title = str(row["title"]).replace("\n", " ")
            label = f"{title} (~{dkm:.1f} км)"
            if len(label) > 64:
                label = label[:61] + "…"
            kb.button(text=label, callback_data=f"gxs:{mode}:{rid}")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def rating_stars_keyboard(trip_id: int, rated_tg_user_id: int) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        for s in range(1, 6):
            kb.button(text=str(s), callback_data=f"rate:{trip_id}:{rated_tg_user_id}:{s}")
        kb.adjust(5)
        return kb.as_markup()

    @staticmethod
    def account_menu_keyboard(*, show_become_driver: bool) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.button(text="Рейтинг", callback_data="account:rating")
        kb.button(text="Оценки обо мне", callback_data="account:reviews")
        kb.button(text="Имя в сервисе", callback_data="account:name")
        if show_become_driver:
            kb.button(text="Стать водителем", callback_data="account:upgrade_driver")
        kb.button(text="⬅ Главное меню", callback_data="account:main_menu")
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def account_back_keyboard() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅ В аккаунт", callback_data="account:root")
        kb.button(text="⬅ Главное меню", callback_data="account:main_menu")
        kb.adjust(1)
        return kb.as_markup()
