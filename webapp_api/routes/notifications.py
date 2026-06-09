"""Агрегированные уведомления пользователя из броней, отмен и оценок."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from app.formatting import format_trip_when
from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.serializers import pending_rating_to_dict, rating_to_dict

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _parse_event_dt(raw: str | None) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _within_days(dt: datetime | None, days: int) -> bool:
    if dt is None:
        return False
    return dt >= datetime.now() - timedelta(days=days)


@router.get("")
def list_notifications(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict[str, list[dict[str, Any]]]:
    tg_id = auth.tg_user_id
    items: list[dict[str, Any]] = []

    prompts = repo.ratings.list_pending_rating_prompts()
    for p in prompts:
        if p.rater_tg_user_id != tg_id:
            continue
        card = repo.trips.get_trip_public_card(p.trip_id)
        pending = pending_rating_to_dict(p, trip_row=card)
        when = pending.get("whenLabel") or "—"
        route = ""
        if pending.get("fromTitle") and pending.get("toTitle"):
            route = f"{pending['fromTitle']} → {pending['toTitle']}"
        body = f"Как прошла поездка с {p.rated_name}?"
        if route:
            body += f" {route}"
        if when != "—":
            body += f" · {when}"
        items.append(
            {
                "id": f"rating_pending:{p.trip_id}:{p.rated_tg_user_id}",
                "kind": "rating",
                "title": "Оцените поездку",
                "body": body,
                "occurredAt": datetime.now().isoformat(timespec="seconds"),
                "unread": True,
                "tripId": p.trip_id,
                "action": "rate",
            }
        )

    for row in repo.ratings.list_ratings_received(tg_id):
        rating = rating_to_dict(row)
        when = format_trip_when(row["trip_date"], row["departure_time"], None)
        from_name = rating.get("fromName") or "Пользователь"
        stars = rating.get("stars", 0)
        items.append(
            {
                "id": f"rating_received:{rating['tripId']}:{rating.get('createdAt')}",
                "kind": "rating",
                "title": "Новая оценка",
                "body": f"{from_name} поставил(а) {stars}★ · {when}",
                "occurredAt": rating.get("createdAt") or "",
                "unread": False,
                "tripId": rating.get("tripId"),
            }
        )

    for row in repo.bookings.list_driver_booking_notification_events(tg_id):
        when = format_trip_when(row["trip_date"], row["departure_time"], row["time_slot"])
        route = f"{row['start_title']} → {row['end_title']}"
        passenger = row["passenger_name"] or "Пассажир"
        if row["status"] == "active":
            items.append(
                {
                    "id": f"booking_new:{row['booking_id']}",
                    "kind": "booking",
                    "title": "Новый пассажир",
                    "body": f"{passenger} забронировал(а) место · {route} · {when}",
                    "occurredAt": row["created_at"],
                    "unread": False,
                    "tripId": row["trip_id"],
                    "action": "manage",
                }
            )
        elif row["status"] == "cancelled_by_passenger":
            reason = (row["cancel_reason"] or "").strip()
            reason_part = f" Причина: «{reason}»." if reason else ""
            items.append(
                {
                    "id": f"booking_cancel_passenger:{row['booking_id']}",
                    "kind": "cancel",
                    "title": "Бронь отменена",
                    "body": f"{passenger} отменил(а) бронь · {route} · {when}.{reason_part}",
                    "occurredAt": row["cancelled_at"],
                    "unread": False,
                    "tripId": row["trip_id"],
                    "action": "manage",
                }
            )

    for row in repo.bookings.list_passenger_booking_notification_events(tg_id):
        when = format_trip_when(row["trip_date"], row["departure_time"], row["time_slot"])
        route = f"{row['start_title']} → {row['end_title']}"
        driver = row["driver_name"] or "Водитель"
        reason = (row["cancel_reason"] or "").strip()
        reason_part = f" Причина: «{reason}»." if reason else ""
        items.append(
            {
                "id": f"booking_cancel_driver:{row['booking_id']}",
                "kind": "cancel",
                "title": "Поездка отменена",
                "body": f"{driver} отменил(а) бронь · {route} · {when}.{reason_part}",
                "occurredAt": row["cancelled_at"],
                "unread": False,
                "tripId": row["trip_id"],
                "action": "bookings",
            }
        )

    items = [n for n in items if _within_days(_parse_event_dt(n.get("occurredAt")), 14) or n.get("unread")]
    items.sort(key=lambda n: _parse_event_dt(n.get("occurredAt")) or datetime.min, reverse=True)
    return {"notifications": items[:50]}
