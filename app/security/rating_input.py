"""Валидация данных для оценок поездок (callback и текст отзыва)."""

from __future__ import annotations

import re

# Telegram message length is large; для SQLite и UI держим разумный потолок.
MAX_REVIEW_CHARS = 500

# Telegram user id в текущей эпохе укладывается в int64; trip_id — в пределах SQLite INTEGER.
_MAX_TRIP_ID = 2_147_483_647
_MAX_TG_USER_ID = 9_999_999_999_999


def parse_rate_callback_data(data: str) -> tuple[int, int, int] | None:
    """Разбирает callback_data вида rate:trip_id:rated_tg_user_id:stars. Возвращает None при некорректных данных."""
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "rate":
        return None
    try:
        trip_id = int(parts[1])
        rated_tg = int(parts[2])
        stars = int(parts[3])
    except ValueError:
        return None
    if trip_id < 1 or trip_id > _MAX_TRIP_ID:
        return None
    if rated_tg < 1 or rated_tg > _MAX_TG_USER_ID:
        return None
    if stars < 1 or stars > 5:
        return None
    return trip_id, rated_tg, stars


_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def normalize_review_text(text: str | None) -> str | None:
    """Обрезка, удаление управляющих символов; «-» или пусто → без текста отзыва."""
    if text is None:
        return None
    s = text.strip()
    if not s or s == "-":
        return None
    s = _CTRL_RE.sub("", s)
    if len(s) > MAX_REVIEW_CHARS:
        s = s[:MAX_REVIEW_CHARS]
    return s
