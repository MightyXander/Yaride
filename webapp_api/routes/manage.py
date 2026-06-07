"""Управление поездками водителя: список своих поездок и брони по поездке."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.repo import Repo
from webapp_api.auth import TelegramAuthUser
from webapp_api.deps import get_auth_user, get_repo
from webapp_api.serializers import driver_trip_to_dict

router = APIRouter(prefix="/api/manage", tags=["manage"])


@router.get("/trips")
def my_trips(
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = repo.trips.list_driver_trips(auth.tg_user_id)
    return {"trips": [driver_trip_to_dict(r) for r in rows]}


@router.get("/trips/{trip_id}/bookings")
def trip_bookings(
    trip_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Активные/прошлые брони на поездку водителя (с рейтингом пассажира)."""
    rows = repo.bookings.list_bookings_for_driver_trip(auth.tg_user_id, trip_id)
    out = []
    for r in rows:
        keys = r.keys()
        out.append(
            {
                "bookingId": r["booking_id"] if "booking_id" in keys else r["id"] if "id" in keys else None,
                "status": r["status"] if "status" in keys else None,
                "passengerName": r["passenger_name"]
                if "passenger_name" in keys
                else r["name"]
                if "name" in keys
                else None,
                "passengerRating": round(float(r["rating_avg"]), 2)
                if "rating_avg" in keys and r["rating_avg"] is not None
                else None,
            }
        )
    return {"bookings": out}


@router.post("/bookings/{booking_id}/reject")
def reject_booking(
    booking_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Водитель отклоняет бронь пассажира (пассажир уведомляется ботом отдельно)."""
    try:
        info = repo.bookings.reject_booking_by_driver(auth.tg_user_id, booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "passengerTgUserId": info.get("passenger_tg_user_id")}


@router.post("/trips/{trip_id}/cancel")
def cancel_trip(
    trip_id: int,
    auth: TelegramAuthUser = Depends(get_auth_user),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Водитель полностью отменяет поездку; все активные брони аннулируются."""
    try:
        affected = repo.trips.cancel_trip_by_driver(auth.tg_user_id, trip_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "affectedPassengers": affected}
