"""Уведомления пользователям в Telegram при действиях из Mini App API."""

from __future__ import annotations

import logging
from typing import Any

from app.formatting import format_trip_when

logger = logging.getLogger(__name__)


class BotNotifier:
    """Тонкая обёртка над aiogram.Bot — ошибки доставки не ломают API-ответ."""

    def __init__(self, bot_token: str | None) -> None:
        self._token = bot_token
        self._bot = None

    @property
    def enabled(self) -> bool:
        return self._token is not None

    def _ensure_bot(self):
        if self._bot is None and self._token:
            from aiogram import Bot

            self._bot = Bot(token=self._token)
        return self._bot

    async def send(self, tg_user_id: int, text: str) -> None:
        bot = self._ensure_bot()
        if bot is None:
            return
        try:
            await bot.send_message(tg_user_id, text)
        except Exception as err:
            logger.warning("WebApp notify failed tg=%s: %s", tg_user_id, err)

    async def close(self) -> None:
        if self._bot is not None:
            await self._bot.session.close()
            self._bot = None

    async def booking_created(
        self,
        *,
        driver_tg_user_id: int,
        passenger_tg_user_id: int,
        booking_id: int,
        trip_id: int,
        start_title: str,
        end_title: str,
        trip_date: str | None,
        departure_time: str | None,
        time_slot: str | None = None,
    ) -> None:
        when = format_trip_when(trip_date, departure_time, time_slot)
        route = f"{start_title} → {end_title}"
        await self.send(
            driver_tg_user_id,
            (
                "Новый пассажир забронировал место.\n"
                f"Поездка #{trip_id} · {route} · {when}"
            ),
        )
        await self.send(
            passenger_tg_user_id,
            f"Бронь #{booking_id} создана.\n{route} · {when}",
        )

    async def booking_cancelled_by_passenger(self, payload: dict[str, Any]) -> None:
        when = format_trip_when(
            payload.get("trip_date"),
            payload.get("departure_time"),
            payload.get("time_slot"),
        )
        reason = str(payload.get("reason") or "").strip()
        reason_part = f"\nПричина: {reason}" if reason else ""
        await self.send(
            int(payload["driver_tg_user_id"]),
            (
                "Пассажир отменил бронь.\n"
                f"Поездка #{payload['trip_id']} · {payload['start_title']} → {payload['end_title']} · {when}"
                f"{reason_part}"
            ),
        )

    async def booking_rejected_by_driver(self, payload: dict[str, Any]) -> None:
        when = format_trip_when(
            payload.get("trip_date"),
            payload.get("departure_time"),
            payload.get("time_slot"),
        )
        await self.send(
            int(payload["passenger_tg_user_id"]),
            (
                "Водитель отклонил твою бронь.\n"
                f"Поездка #{payload['trip_id']} · {payload['start_title']} → {payload['end_title']} · {when}"
            ),
        )

    async def trip_cancelled_by_driver(self, trip_id: int, passenger_tg_ids: list[int]) -> None:
        for tg_uid in passenger_tg_ids:
            await self.send(
                tg_uid,
                f"Водитель отменил поездку #{trip_id}. Твоя бронь аннулирована.",
            )

    async def rating_received(
        self,
        *,
        rated_tg_user_id: int,
        rater_name: str,
        stars: int,
        trip_id: int,
        when_label: str,
        review_text: str | None = None,
    ) -> None:
        body = f"{rater_name} поставил(а) {stars}★ · {when_label}"
        review = (review_text or "").strip()
        if review:
            body += f"\n«{review}»"
        body += f"\nПоездка #{trip_id}"
        await self.send(rated_tg_user_id, body)

    async def route_alert_matched(
        self,
        *,
        passenger_tg_user_id: int,
        trip_id: int,
        from_title: str,
        to_title: str,
        trip_date: str,
        departure_time: str,
        miniapp_url: str | None = None,
    ) -> None:
        """Уведомление пассажиру о появлении поездки по подписке на маршрут."""
        route = f"{from_title} → {to_title}"
        when = format_trip_when(trip_date, departure_time, None)
        body = f"Появилась поездка по твоему запросу!\n{route} · {when}\nПоездка #{trip_id}"

        if miniapp_url:
            deep_link = f"{miniapp_url}#/trip/{trip_id}"
            body += f"\n\nОткрыть: {deep_link}"

        await self.send(passenger_tg_user_id, body)
