"""Преобразование строк БД (sqlite3.Row) в JSON-словари для фронтенда Mini App."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.driver_access import driver_moderation_status
from app.formatting import _time_from_departure_or_slot, effective_min_passenger_rating, format_trip_when


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
        "minPassengerRating": effective_min_passenger_rating(_get(row, "min_passenger_rating")),
        "driverModerationStatus": driver_moderation_status(row),
        "isActiveDriver": row["role"] == "driver" and driver_moderation_status(row) == "approved",
        "dlSeriesNumber": _get(row, "dl_series_number"),
        "dlValidUntil": _get(row, "dl_valid_until"),
    }


def _route_coords(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "startLat": float(_get(row, "start_lat")) if _get(row, "start_lat") is not None else None,
        "startLng": float(_get(row, "start_lng")) if _get(row, "start_lng") is not None else None,
        "endLat": float(_get(row, "end_lat")) if _get(row, "end_lat") is not None else None,
        "endLng": float(_get(row, "end_lng")) if _get(row, "end_lng") is not None else None,
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
        **_route_coords(row),
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
        **_route_coords(row),
    }


def driver_trip_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    seats_total = int(_get(row, "seats_total", 0) or 0)
    seats_booked = int(_get(row, "seats_booked", 0) or 0)
    trip_date = _get(row, "trip_date")
    departure_time = _get(row, "departure_time")
    time_slot = _get(row, "time_slot")
    return {
        "id": row["id"],
        "fromTitle": _get(row, "start_title"),
        "toTitle": _get(row, "end_title"),
        "tripDate": trip_date,
        "departureTime": _time_from_departure_or_slot(departure_time, time_slot),
        "whenLabel": format_trip_when(trip_date, departure_time, time_slot),
        "priceRub": int(_get(row, "price_rub", 0) or 0),
        "seatsTotal": seats_total,
        "seatsFree": max(0, seats_total - seats_booked),
        "seatsBooked": seats_booked,
        "status": _get(row, "status"),
        "driverName": _get(row, "driver_name"),
        "driverRating": round(float(_get(row, "driver_rating", 0.0) or 0.0), 2),
        **_route_coords(row),
    }


def rating_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "stars": int(_get(row, "stars", 0) or 0),
        "tripId": _get(row, "trip_id"),
        "reviewText": _get(row, "review_text"),
        "createdAt": _get(row, "created_at"),
        "fromName": _get(row, "rater_name") or _get(row, "name"),
    }


def history_passenger_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    seats_total = int(_get(row, "seats_total", 0) or 0)
    seats_booked = int(_get(row, "seats_booked", 0) or 0)
    my_stars = _get(row, "my_rating_stars")
    return {
        "bookingId": row["booking_id"],
        "tripId": row["trip_id"],
        "bookingStatus": _get(row, "booking_status"),
        "tripStatus": _get(row, "trip_status"),
        "cancelReason": _get(row, "cancel_reason"),
        "fromTitle": _get(row, "start_title"),
        "toTitle": _get(row, "end_title"),
        "tripDate": _get(row, "trip_date"),
        "departureTime": _get(row, "departure_time"),
        "whenLabel": format_trip_when(_get(row, "trip_date"), _get(row, "departure_time"), _get(row, "time_slot")),
        "priceRub": int(_get(row, "price_rub", 0) or 0),
        "seatsTotal": seats_total,
        "seatsFree": max(0, seats_total - seats_booked),
        "driverName": _get(row, "driver_name"),
        "driverRating": round(float(_get(row, "driver_rating", 0.0) or 0.0), 2),
        "driverTgUserId": _get(row, "driver_tg_user_id"),
        "myRatingStars": int(my_stars) if my_stars is not None else None,
        "canRate": my_stars is None and _get(row, "driver_tg_user_id") is not None,
    }


def history_driver_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    seats_total = int(_get(row, "seats_total", 0) or 0)
    seats_booked = int(_get(row, "seats_booked", 0) or 0)
    return {
        "tripId": row["trip_id"],
        "tripStatus": _get(row, "trip_status"),
        "fromTitle": _get(row, "start_title"),
        "toTitle": _get(row, "end_title"),
        "tripDate": _get(row, "trip_date"),
        "departureTime": _get(row, "departure_time"),
        "whenLabel": format_trip_when(_get(row, "trip_date"), _get(row, "departure_time"), _get(row, "time_slot")),
        "priceRub": int(_get(row, "price_rub", 0) or 0),
        "seatsTotal": seats_total,
        "seatsBooked": seats_booked,
        "seatsFree": max(0, seats_total - seats_booked),
    }


def pending_rating_to_dict(prompt, *, trip_row: sqlite3.Row | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "tripId": prompt.trip_id,
        "ratedTgUserId": prompt.rated_tg_user_id,
        "ratedName": prompt.rated_name,
    }
    if trip_row is not None:
        out.update(
            {
                "fromTitle": _get(trip_row, "start_title"),
                "toTitle": _get(trip_row, "end_title"),
                "whenLabel": format_trip_when(
                    _get(trip_row, "trip_date"),
                    _get(trip_row, "departure_time"),
                    _get(trip_row, "time_slot"),
                ),
                "driverName": _get(trip_row, "driver_name"),
            }
        )
    return out
