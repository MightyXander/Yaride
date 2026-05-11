"""FSM-состояния бота (этап 3 — вынесены из bot.py)."""

from aiogram.fsm.state import State, StatesGroup


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
