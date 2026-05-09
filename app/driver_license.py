from __future__ import annotations

import re
from datetime import date, datetime


def normalize_license_number(raw: str) -> str:
    """Убираем лишние пробелы, проверяем минимальную длину номера ВУ (без запросов в ГИБДД)."""
    cleaned = re.sub(r"\s+", " ", (raw or "").strip())
    if len(cleaned) < 5:
        raise ValueError("Номер водительского удостоверения слишком короткий.")
    if not re.match(r"^[\dA-Za-zА-Яа-яЁё №\-.\s]+$", cleaned):
        raise ValueError("Номер содержит недопустимые символы.")
    return cleaned


def parse_valid_until_iso(text: str) -> date:
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Некорректная дата. Используй формат ГГГГ-ММ-ДД.") from exc


def assert_license_not_expired(valid_until: date, *, today: date | None = None) -> None:
    day = today or date.today()
    if valid_until < day:
        raise ValueError("Срок действия водительского удостоверения уже истёк.")
