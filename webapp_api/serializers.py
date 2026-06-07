"""Преобразование строк БД (sqlite3.Row) в JSON-словари для фронтенда Mini App."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.formatting import format_trip_when


def _get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def user_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tgUserId": row["tg_user_id"],
        "name": row["name"],
        "username": _get(row, "username"),
        "role": row["role"],
        "ratingAvg": round(float(_get(row, "rating_avg", 0.0) or 0.0), 2),
        "ratingCount": int(_get(row, "rating_count", 0) or 0),
        "tripsDriverCount": int(_get(row, "trips_driver_count", 0) or 0),
        "tripsPassengerCount": int(_get(row, "trips_passenger_count", 0) or 0),
        "carModel": _get(row, "car_model"),
        "carColor": _get(row, "car_color"),
        "carPlate": _get(row, "car_plate"),
        "isBanned": bool(_get(row, "is_banned", 0)),
    }


def trip_card_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Карточка поездки для списков поиска/деталей."""
    seats_total = int(_get(row, "seats_total", 0) or 0)
    seats_booked = int(_get(row, "seats_booked", 0) or 0)
    return {
        "id": row["id"],
        "fromTitle": _get(row, "start_title"),
        "toTitle": _get(row, "end_title"),
        "tripDate": _get(row, "trip_date"),
        "departureTime": _get(row, "departure_time"),
        "whenLabel": format_trip_when(_get(row, "trip_date"), _get(row, "departure_time"), _get(row, "time_slot")),
        "priceRub": int(_get(row, "price_rub", 0) or 0),
        "seatsTotal": seats_total,
        "seatsFree": max(0, seats_total - seats_booked),
        "status": _get(row, "status"),
        "driverName": _get(row, "driver_name"),
        "driverRating": round(float(_get(row, "driver_rating", 0.0) or 0.0), 2),
        "comment": _get(row, "comment"),
        "carModel": _get(row, "car_model"),
        "carColor": _get(row, "car_color"),
        "carPlate": _get(row, "car_plate"),
    }


def booking_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tripId": _get(row, "trip_id"),
        "status": _get(row, "status"),
        "cancelReason": _get(row, "cancel_reason"),
        "fromTitle": _get(row, "start_title"),
        "toTitle": _get(row, "end_title"),
        "whenLabel": format_trip_when(_get(row, "trip_date"), _get(row, "departure_time"), _get(row, "time_slot")),
        "priceRub": int(_get(row, "price_rub", 0) or 0),
        "driverName": _get(row, "driver_name"),
    }


def driver_trip_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    seats_total = int(_get(row, "seats_total", 0) or 0)
    seats_booked = int(_get(row, "seats_booked", 0) or 0)
    return {
        "id": row["id"],
        "fromTitle": _get(row, "start_title"),
        "toTitle": _get(row, "end_title"),
        "whenLabel": format_trip_when(_get(row, "trip_date"), _get(row, "departure_time"), _get(row, "time_slot")),
        "priceRub": int(_get(row, "price_rub", 0) or 0),
        "seatsTotal": seats_total,
        "seatsFree": max(0, seats_total - seats_booked),
        "seatsBooked": seats_booked,
        "status": _get(row, "status"),
    }


def rating_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "stars": int(_get(row, "stars", 0) or 0),
        "tripId": _get(row, "trip_id"),
        "reviewText": _get(row, "review_text"),
        "createdAt": _get(row, "created_at"),
        "fromName": _get(row, "rater_name") or _get(row, "name"),
    }
