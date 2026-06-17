"""Продуктовая аналитика: лёгкий best-effort лог событий воронки.

События пишутся в таблицу ``analytics_events`` в отдельной короткой транзакции —
уже после коммита доменного действия, чтобы не вкладываться в чужую транзакцию и не
влиять на её атомарность. Логирование никогда не должно ломать продуктовый сценарий:
любая ошибка глотается и пишется в ``logger.warning``.

Воронка: ``search`` → (results>0) → ``booking_created`` → (потом) ``trip_completed``.
``booking_cancelled`` — отвал на этапе брони. Пустой поиск виден как ``search`` с
``props.results == 0``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import DbHandle

logger = logging.getLogger(__name__)

# Имена событий — единый источник правды для записи и для построения воронки.
EVENT_SEARCH = "search"
EVENT_TRIP_CREATED = "trip_created"
EVENT_BOOKING_CREATED = "booking_created"
EVENT_BOOKING_CANCELLED = "booking_cancelled"


def record_event(
    db: DbHandle,
    event: str,
    *,
    tg_user_id: int | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    """Записать продуктовое событие. Best-effort: ошибки не пробрасываются.

    ``props`` сериализуется в JSON-текст (совместимо и со SQLite, и с PostgreSQL).
    Плейсхолдер ``?`` для PostgreSQL транслируется адаптером соединения в ``%s``.
    """
    try:
        props_json = json.dumps(props, ensure_ascii=False) if props else None
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO analytics_events(event, tg_user_id, props) VALUES (?, ?, ?)",
                (event, tg_user_id, props_json),
            )
    except Exception as exc:  # noqa: BLE001 — аналитика не должна ронять бизнес-логику
        logger.warning("analytics: не удалось записать событие %s: %s", event, exc)
