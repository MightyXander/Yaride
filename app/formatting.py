"""Форматирование данных поездок для отображения пользователю.

Отдельный модуль, чтобы логика форматирования не дублировалась в хендлерах
и могла быть покрыта тестами без Telegram-контекста.
"""

from __future__ import annotations

from datetime import date

_WEEKDAYS_RU = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)


def _parse_date_from_string(raw: str | None) -> date | None:
    """Допускает формат с временным компонентом (ISO 8601 со временем) и пробелом — из-за разных источников БД."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "T" in s:
        s = s.split("T", 1)[0]
    elif " " in s:
        s = s.split()[0]
    s = s[:10]
    if len(s) != 10:
        return None
    try:
        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
        return date(y, m, d)
    except ValueError:
        return None


def _time_from_departure_or_slot(departure_time: str | None, time_slot: str | None) -> str | None:
    """departure_time — приоритетное поле; time_slot используется как запасной источник (обратная совместимость)."""
    if departure_time and str(departure_time).strip():
        return str(departure_time).strip()
    if not time_slot or not str(time_slot).strip():
        return None
    parts = str(time_slot).split()
    for tok in reversed(parts):
        if ":" in tok and len(tok) <= 8:
            return tok
    return None


def format_trip_when(
    trip_date: str | None = None,
    departure_time: str | None = None,
    time_slot: str | None = None,
) -> str:
    """Человекочитаемо: «Вторник 05-08 13:00» (без года)."""
    d = _parse_date_from_string(trip_date)
    tm = _time_from_departure_or_slot(departure_time, time_slot)
    if d is None and time_slot:
        d = _parse_date_from_string(time_slot.split()[0] if time_slot else None)
    if d is None:
        return tm if tm else "—"
    wd = _WEEKDAYS_RU[d.weekday()]
    label = f"{wd} {d.month:02d}-{d.day:02d}"
    if tm:
        return f"{label} {tm}"
    return label


def format_trip_row(row) -> str:
    keys = row.keys()
    return format_trip_when(
        row["trip_date"] if "trip_date" in keys else None,
        row["departure_time"] if "departure_time" in keys else None,
        row["time_slot"] if "time_slot" in keys else None,
    )


def passenger_rating_hint(row) -> str:
    """Подпись «X.Y, оценок: N» (или «нет оценок») для строки с `rating_count` и `rating_avg`."""
    rc = int(row["rating_count"] or 0)
    ra = float(row["rating_avg"] or 0.0)
    if rc == 0:
        return "нет оценок"
    return f"{ra:.1f}, оценок: {rc}"
